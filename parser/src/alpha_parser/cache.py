"""Portable JSON cache with atomic writes, TTL and per-key process locks."""
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time


class CacheBusyError(TimeoutError):
    pass


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _file_signature(path):
    stat = path.stat()
    return tuple(getattr(stat, key) for key in ("st_size", "st_mtime_ns", "st_ctime_ns", "st_ino", "st_dev"))


def _hash_stable_file(path_text, signature):
    path = Path(path_text)
    if _file_signature(path) != signature:
        raise ValueError("Input changed before computing its fingerprint")
    with path.open("rb") as stream:
        result = hashlib.file_digest(stream, "sha256").hexdigest()
    if _file_signature(path) != signature:
        raise ValueError("Input changed while computing its content fingerprint")
    return result


def file_sha256(path):
    path = Path(path).resolve()
    signature = _file_signature(path)
    result = _hash_stable_file(str(path), signature)
    if _file_signature(path) != signature:
        raise ValueError("Input changed while retrieving its content fingerprint")
    return result


def code_fingerprint(paths):
    return fingerprint(sorted((Path(path).name, file_sha256(path)) for path in paths))


@contextmanager
def atomic_file(path):
    """Replace a text file only after a successful write and flush."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=path.name + ".", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                temporary = None
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(.05 * 2 ** attempt)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def atomic_json(path, payload):
    with atomic_file(path) as stream:
        json.dump(payload, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def atomic_text(path, text):
    with atomic_file(path) as stream:
        stream.write(text)


@contextmanager
def file_lock(path, timeout=30):
    """OS releases the lock after process death; no stale-lock file deletion."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    deadline = time.monotonic() + timeout
    acquired = False
    try:
        while not acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    raise CacheBusyError("Another inference process is using this cache key") from None
                time.sleep(.05)
        yield
    finally:
        if acquired:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


class JsonCache:
    def __init__(self, root, lock_timeout=30):
        self.root = Path(root).resolve()
        self.lock_timeout = lock_timeout
        self.stats = {"hits": 0, "misses": 0, "writes": 0}

    def _path(self, namespace, key):
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", namespace):
            raise ValueError("Invalid cache namespace")
        return self.root / namespace / (fingerprint(key) + ".json")

    @contextmanager
    def lock(self, namespace, key, timeout=None):
        path = self._path(namespace, key).with_suffix(".lock")
        with file_lock(path, self.lock_timeout if timeout is None else timeout):
            yield

    def _read(self, namespace, key, ttl=None):
        path = self._path(namespace, key)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError, OSError):
            return None
        if not isinstance(record, dict) or record.get("format") != 1 or record.get("key") != fingerprint(key):
            return None
        created = record.get("created_at")
        if not isinstance(created, (int, float)):
            return None
        now = time.time()
        expires = record.get("expires_at")
        if expires is not None and (not isinstance(expires, (int, float)) or now >= expires):
            return None
        if ttl is not None and now - created >= ttl:
            return None
        return record.get("payload")

    def get(self, namespace, key, ttl=None):
        result = self._read(namespace, key, ttl)
        self.stats["hits" if result is not None else "misses"] += 1
        return copy.deepcopy(result)

    def put(self, namespace, key, payload, ttl=None):
        created = time.time()
        atomic_json(self._path(namespace, key),
                    {"format": 1, "key": fingerprint(key), "created_at": created,
                     "expires_at": created + ttl if ttl is not None else None, "payload": payload})
        self.stats["writes"] += 1

    def get_or_compute(self, namespace, key, compute, ttl=None):
        with self.lock(namespace, key):
            value = self.get(namespace, key, ttl)
            if value is not None:
                return value, True
            value = compute()  # Failures are never recorded as successful cache values.
            self.put(namespace, key, value, ttl)
            return copy.deepcopy(value), False

    def invalidate(self, namespace, key):
        with self.lock(namespace, key):
            self._path(namespace, key).unlink(missing_ok=True)

    def update(self, namespace, key, function, default=None):
        with self.lock(namespace, key):
            payload = self._read(namespace, key)
            value = function(copy.deepcopy(default if payload is None else payload))
            self.put(namespace, key, value)
            return copy.deepcopy(value)
