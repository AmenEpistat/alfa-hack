"""In-memory source records with explicit, portable JSON stage snapshots."""
import copy
import hashlib
import json
import math
import re
import threading
import time
import uuid
from pathlib import Path
from .schemas import Chunk, Document, WatchCompany
from .cache import JsonCache, atomic_json as write_json


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


class Store:
    """One sequential pipeline workspace; no database, SQL driver or server.

    02_sources.json is a self-contained source stage: exact document versions,
    extracted pages/tables/chunks, watchlist and local usage ledger.
    03_parser.json is the latest research checkpoint. Different independent runs
    should use separate output directories. Processes must not write one directory
    concurrently.
    """

    def __init__(self, root: Path, *, cache_dir=None, budget_scope="default", tenant_scope="default"):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._cache = {}
        self.cache_dir = Path(cache_dir).resolve() if cache_dir is not None else None
        self.cache = JsonCache(self.cache_dir) if self.cache_dir is not None else None
        self.budget_scope, self.tenant_scope = budget_scope, tenant_scope
        self.sources = []
        self.state = {"schema_version": "1.0", "stage": "sources",
                      "identities": {}, "current_versions": {}, "documents": {},
                      "chunks": {}, "watches": {}, "watch_defaults": {},
                      "company_profiles": {}, "spend": {}}
        path = self.root / "02_sources.json"
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if loaded.get("schema_version") != "1.0" or loaded.get("stage") != "sources":
                raise ValueError("Unsupported source-stage JSON")
            self.state.update(loaded)
        self._runs = {}
        path = self.root / "03_parser.json"
        if path.exists():
            run = json.loads(path.read_text(encoding="utf-8"))
            if run.get("run_id"):
                self._runs[run["run_id"]] = run

    def flush(self):
        with self._lock:
            write_json(self.root / "02_sources.json", self.state)

    def original(self, content: bytes, suffix: str) -> str:
        folder = (self.cache.root if self.cache is not None else self.root) / "originals"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (digest(content) + suffix)
        try:
            with path.open("xb") as handle:
                handle.write(content)
        except FileExistsError:
            pass
        return str(path)

    def _load_document(self, document: dict) -> dict:
        document = copy.deepcopy(document)
        name = Path(str(document.get("original_path") or "").replace("\\", "/")).name
        local = self.root / "originals" / name
        if local.is_file():
            document["original_path"] = str(local)
        elif self.cache is not None and (self.cache.root / "originals" / name).is_file():
            document["original_path"] = str(self.cache.root / "originals" / name)
        return document

    def version(self, version_id: str) -> dict | None:
        doc = self.state["documents"].get(version_id)
        return self._load_document(doc) if doc else None

    def chunks(self, version_id: str) -> list[dict]:
        return [copy.deepcopy(chunk) for chunk in self.state["chunks"].values()
                if chunk["version_id"] == version_id]

    def processed(self, hash_: str, extractor: str, config: str) -> dict | None:
        for doc in reversed(list(self.state["documents"].values())):
            if (doc["content_hash"], doc["extractor_version"], doc["config_hash"]) == (hash_, extractor, config) and doc["quality"] != "failed":
                return self._load_document(doc)
        return None

    def update_document(self, version_id: str, **changes):
        with self._lock:
            self.state["documents"][version_id].update(copy.deepcopy(changes))
            self.flush()

    def save_document(self, identity: str, doc: Document, chunks: list[Chunk], force=False) -> dict:
        with self._lock:
            doc.document_id = self.state["identities"].get(identity) or str(uuid.uuid4())
            previous = self.state["current_versions"].get(doc.document_id)
            if previous:
                old = self.version(previous)
                if not force and all(old.get(k) == getattr(doc, k) for k in ("content_hash", "extractor_version", "config_hash", "title", "published_at", "original_filename", "author")):
                    return {"document": old, "skipped": True}
            doc.previous_version_id = previous
            doc.version_id = str(uuid.uuid4())
            normalized = " ".join(" ".join(x.text for x in chunks).casefold().split())
            doc.duplicate_group = digest(normalized) if normalized else None
            payload = doc.model_dump(mode="json")
            try:
                payload["original_path"] = Path(doc.original_path).resolve().relative_to(self.root).as_posix()
            except ValueError:
                if self.cache is not None:
                    try:
                        payload["original_path"] = Path(doc.original_path).resolve().relative_to(self.cache.root).as_posix()
                    except ValueError:
                        pass
            self.state["identities"][identity] = doc.document_id
            self.state["documents"][doc.version_id] = payload
            for i, chunk in enumerate(chunks):
                chunk.document_id, chunk.version_id = doc.document_id, doc.version_id
                chunk.chunk_id = digest(f"{doc.version_id}:{i}")[:32]
                self.state["chunks"][chunk.chunk_id] = chunk.model_dump(mode="json")
            if doc.quality != "failed" or previous is None:
                self.state["current_versions"][doc.document_id] = doc.version_id
            self.flush()
            return {"document": self._load_document(payload), "skipped": False, "chunks": len(chunks)}

    def documents(self, history=False) -> list[dict]:
        ids = self.state["documents"] if history else self.state["current_versions"].values()
        return [self.version(id_) for id_ in ids]

    def chunk(self, id_: str) -> dict | None:
        return copy.deepcopy(self.state["chunks"].get(id_))

    def search(self, query: str, source_type=None, start=None, end=None, limit=15) -> list[dict]:
        terms = set(re.findall(r"\w+", query.casefold())[:24])
        if not terms:
            return []
        candidates = []
        for doc in self.documents():
            if doc["quality"] == "failed" or source_type and doc["source_type"] != source_type:
                continue
            published = doc.get("published_at")
            if published and ((start and published[:10] < str(start)) or (end and published[:10] > str(end))):
                continue
            for chunk in self.chunks(doc["version_id"]):
                words = re.findall(r"\w+", chunk["text"].casefold())
                counts = {term: words.count(term) for term in terms}
                matched = sum(count > 0 for count in counts.values())
                if matched:
                    score = matched + sum(math.log1p(count) for count in counts.values()) / math.log2(len(words) + 2)
                    candidates.append((score, doc, chunk))
        candidates.sort(key=lambda row: row[0], reverse=True)
        result, dedup = [], {}
        for _, doc, chunk in candidates:
            key = (doc.get("duplicate_group"), " ".join(chunk["text"].casefold().split()))
            if key in dedup:
                dedup[key]["alternate_sources"].append({k: doc[k] for k in ("document_id", "version_id", "url", "source_name")})
                continue
            hit = {"chunk": chunk, "document": doc, "date_in_range": True if doc.get("published_at") else None,
                   "alternate_sources": []}
            dedup[key] = hit
            result.append(hit)
            if len(result) >= limit:
                break
        return result

    def source_bundle(self, document):
        """Copy only public source evidence and its immutable original into shared cache."""
        document = copy.deepcopy(document)
        original = Path(document.get("original_path") or "")
        if self.cache is not None and original.is_file():
            folder = self.cache.root / "originals"
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / original.name
            if not target.exists():
                import shutil
                shutil.copy2(original, target)
            document["original_path"] = "originals/" + target.name
        return {"document": document, "chunks": self.chunks(document["version_id"]),
                "identities": [key for key, id_ in self.state["identities"].items() if id_ == document["document_id"]]}

    def import_source(self, bundle, *, flush=True):
        document = Document.model_validate(bundle["document"]).model_dump(mode="json")
        chunks = [Chunk.model_validate(c).model_dump(mode="json") for c in bundle["chunks"]]
        if not document["document_id"] or not document["version_id"]:
            raise ValueError("Cached source is missing identity")
        if any(c["version_id"] != document["version_id"] or c["document_id"] != document["document_id"] for c in chunks):
            raise ValueError("Cached chunks belong to another source version")
        name = Path(document["original_path"].replace("\\", "/")).name
        if self.cache is not None:
            original = self.cache.root / "originals" / name
            if original.is_file():
                document["original_path"] = "originals/" + name
        version = document["version_id"]
        self.state["documents"][version] = document
        self.state["current_versions"][document["document_id"]] = version
        identities = bundle.get("identities", [])
        if not identities:
            identities = (["external:" + document["url"]] if document["source_type"] == "external" else
                          ["alpha:" + document["original_filename"], "alpha:" + Path(document["original_filename"]).stem])
        for identity in identities:
            self.state["identities"].setdefault(identity, document["document_id"])
        self.state["chunks"].update({c["chunk_id"]: c for c in chunks})
        if flush:
            self.flush()
        return self.version(version)

    def load_corpus(self):
        if self.cache is None:
            return
        corpus = self.cache.get("corpus", "public_sources") or {"sources": {}}
        for bundle in corpus["sources"].values():
            self.import_source(bundle, flush=False)
        self.flush()

    def save_corpus(self):
        if self.cache is None:
            return
        bundles = {doc["document_id"]: self.source_bundle(doc) for doc in self.documents() if doc["quality"] != "failed"}

        def change(corpus):
            corpus["sources"].update(bundles)
            return corpus
        self.cache.update("corpus", "public_sources", change, default={"sources": {}})

    def cache_get(self, key):
        if self.cache is not None:
            return self.cache.get("search", key)
        entry = self._cache.get(key)
        return copy.deepcopy(entry["payload"]) if entry and entry["expires"] > time.time() else None

    def cache_put(self, key, payload, expires):
        if self.cache is not None:
            self.cache.put("search", key, payload, ttl=max(0, expires - time.time()))
        else:
            self._cache[key] = {"payload": copy.deepcopy(payload), "expires": expires}

    def _watch_record(self, owner):
        if self.cache is not None:
            result = self.cache.get("watchlists", {"tenant": self.tenant_scope, "owner": owner})
            if result is not None:
                return result
        return {"companies": [copy.deepcopy(w) for w in self.state["watches"].values() if w["owner"] == owner],
                "initialized": owner in self.state["watch_defaults"],
                "catalog_version": self.state["watch_defaults"].get(owner)}

    def _edit_watches(self, owner, change):
        if self.cache is not None:
            record = self.cache.update("watchlists", {"tenant": self.tenant_scope, "owner": owner},
                                       change, default=self._watch_record(owner))
        else:
            record = change(self._watch_record(owner))
        self.state["watches"] = {id_: w for id_, w in self.state["watches"].items() if w["owner"] != owner}
        self.state["watches"].update({w["id"]: w for w in record["companies"]})
        if record["initialized"]:
            self.state["watch_defaults"][owner] = record.get("catalog_version") or "user_edited"
        self.flush()
        return record

    def watches(self, owner: str) -> list[dict]:
        return copy.deepcopy(self._watch_record(owner)["companies"])

    def watch_add(self, owner: str, company: WatchCompany) -> dict:
        item = {"id": str(uuid.uuid4()), "owner": owner, **company.model_dump(mode="json")}

        def change(record):
            record["companies"].append(item)
            record.update(initialized=True, catalog_version="user_defined")
            return record
        self._edit_watches(owner, change)
        return copy.deepcopy(item)

    def watch_defaults_initialized(self, owner):
        return self._watch_record(owner)["initialized"]

    def seed_watches(self, owner, companies, catalog_version):
        def change(record):
            if not record["initialized"]:
                record["companies"] = [
                    {"id": str(uuid.uuid4()), "owner": owner, **company.model_dump(mode="json")}
                    for company in companies]
                record.update(initialized=True, catalog_version=catalog_version)
            return record
        self._edit_watches(owner, change)

    def watch_update(self, owner, id_, company):
        def change(record):
            found = next((w for w in record["companies"] if w["id"] == id_), None)
            if found is None:
                raise KeyError("watch not found for this owner")
            record["companies"] = [w for w in record["companies"] if w["id"] != id_]
            if company is not None:
                record["companies"].append({"id": id_, "owner": owner, **company.model_dump(mode="json")})
            record.update(initialized=True, catalog_version="user_edited")
            return record
        self._edit_watches(owner, change)

    def run_put(self, run):
        self._runs[run["run_id"]] = copy.deepcopy(run)
        self.flush()
        write_json(self.root / "03_parser.json", run)

    def run_get(self, id_):
        return copy.deepcopy(self._runs.get(id_))

    def _budget_update(self, change):
        if self.cache is not None:
            ledger = self.cache.update("budgets", self.budget_scope, change, default={})
        else:
            ledger = change(copy.deepcopy(self.state["spend"]))
        self.state["spend"] = ledger
        self.flush()

    def budget_reserve(self, day, amount, known, limit):
        def change(ledger):
            spend = ledger.setdefault(day, {"reserved": 0., "actual": 0., "unknown_calls": 0})
            if known and spend["unknown_calls"]:
                raise ValueError("Today contains calls with unknown cost; reconcile spend before paid continuation")
            if spend["reserved"] + spend["actual"] + amount > limit:
                raise ValueError("Local daily module budget exhausted")
            spend["reserved"] += amount
            spend["unknown_calls"] += int(not known)
            return ledger
        self._budget_update(change)

    def budget_settle(self, day, reserve, actual=0., release_unknown=0):
        def change(ledger):
            spend = ledger.setdefault(day, {"reserved": 0., "actual": 0., "unknown_calls": 0})
            spend["reserved"] = max(0., spend["reserved"] - reserve)
            spend["actual"] += actual
            spend["unknown_calls"] = max(0, spend["unknown_calls"] - release_unknown)
            return ledger
        self._budget_update(change)
