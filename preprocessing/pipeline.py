"""CSV -> cleaned and enriched company JSON, with optional persistent inference cache."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .cleaning import REQUIRED, clean_rows
from .features import build_features
from .io import read_csv, write_json

SCHEMA_VERSION = "1.0"
PREPROCESSING_VERSION = "1.0"


def _source_signature(path):
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _process_csv(path, checksum, delimiter):
    """Compute all aggregates before choosing a company; cache this full result."""
    records, audit = clean_rows(read_csv(path, delimiter=delimiter, required_columns=REQUIRED))
    build_features(records)
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_type": "company_profiles",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {"name": path.name, "sha256": checksum},
        "preprocessing": {
            "version": PREPROCESSING_VERSION, **audit, "rows_exported": len(records),
            "aggregate_scope": "entire cleaned company CSV, before selecting output companies",
            "feature_notes": [
                "worker_mid_approx and revenue_per_worker use category approximations, not actual headcount.",
                "Revenue 1000 is excluded from computed metrics as an unknown-value placeholder.",
                "Industry/group/region shares describe only the supplied dataset, not market shares.",
                "Open-ended age categories remain null, as in the notebook regex.",
                "okved_sector follows the notebook's coarse mapping; unmatched valid classes map to услуги.",
            ],
        },
        "companies": records,
    }


def _selected_payload(payload, selected):
    """Copy just selected records and the small common metadata."""
    if selected is None:
        return payload
    records = payload["companies"]
    found = {record["company_id"] for record in records}
    if selected - found:
        raise ValueError(f"Companies absent after cleaning: {', '.join(sorted(selected - found))}")
    result = {key: copy.deepcopy(value) for key, value in payload.items() if key != "companies"}
    result["companies"] = [copy.deepcopy(record) for record in records if record["company_id"] in selected]
    result["preprocessing"]["rows_exported"] = len(result["companies"])
    return result


def _valid_payload(payload, checksum, selected=None):
    """Reject structurally corrupt or wrong-source cached profiles before use."""
    if (not isinstance(payload, dict)
            or payload.get("schema_version") != SCHEMA_VERSION
            or payload.get("dataset_type") != "company_profiles"
            or not isinstance(payload.get("source"), dict)
            or payload["source"].get("sha256") != checksum
            or not isinstance(payload.get("preprocessing"), dict)
            or payload["preprocessing"].get("version") != PREPROCESSING_VERSION
            or not isinstance(payload.get("companies"), list)):
        return False
    companies = payload["companies"]
    if payload["preprocessing"].get("rows_exported") != len(companies):
        return False
    ids = []
    for record in companies:
        if (not isinstance(record, dict) or not isinstance(record.get("company_id"), str)
                or not isinstance(record.get("attributes"), dict)
                or not isinstance(record.get("features"), dict)):
            return False
        ids.append(record["company_id"])
    return len(ids) == len(set(ids)) and (selected is None or set(ids) == selected)


def _cached_payload(cache, namespace, key, compute, checksum, selected=None):
    payload, hit = cache.get_or_compute(namespace, key, compute)
    if not _valid_payload(payload, checksum, selected):
        cache.invalidate(namespace, key)
        payload, hit = cache.get_or_compute(namespace, key, compute)
        if not _valid_payload(payload, checksum, selected):
            raise ValueError("Processed CSV cache does not match its schema or source checksum")
    return payload, hit


def preprocess_csv(path, *, output=None, company_ids=None, delimiter=None, cache_dir=None):
    """Select profiles with persistent whole-dataset and small per-selection caches.

    Dataset identity includes source bytes, delimiter and processing code. The
    full dataset is processed once; repeated company requests read only their
    small cached profiles. A changing source never publishes a mismatched result.
    """
    path = Path(path).resolve()
    selected = set(company_ids) if company_ids is not None else None
    if selected is not None and any(not isinstance(value, str) for value in selected):
        raise ValueError("company_ids must contain strings")
    signature = _source_signature(path)
    if cache_dir is not None:
        # Ordinary preprocessing remains usable without the parser installed.
        from alpha_parser.cache import JsonCache, code_fingerprint, file_sha256

        checksum = file_sha256(path)
        package = Path(__file__).parent
        fingerprint = code_fingerprint([
            package / name for name in ("cleaning.py", "features.py", "io.py", "pipeline.py")
        ])
        key = hashlib.sha256(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "preprocessing_version": PREPROCESSING_VERSION,
            "source_sha256": checksum,
            "delimiter": delimiter,
            "processing_code": fingerprint,
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    else:
        checksum = _sha256(path)

    if _source_signature(path) != signature:
        raise ValueError("CSV changed while computing its content hash; retry with a stable input file")

    def compute():
        if _source_signature(path) != signature:
            raise ValueError("CSV changed before processing; retry with a stable input file")
        payload = _process_csv(path, checksum, delimiter)
        if _source_signature(path) != signature or _sha256(path) != checksum:
            raise ValueError("CSV changed during processing; no processed result was cached")
        return payload

    if cache_dir is None:
        payload = _selected_payload(compute(), selected)
    else:
        cache = JsonCache(cache_dir)
        if selected is None:
            payload, hit = _cached_payload(cache, "csv", key, compute, checksum)
            metadata = {"hit": hit, "key": key, "scope": "entire cleaned company CSV"}
        else:
            full_hit = None
            profile_key = {"dataset_key": key, "company_ids": sorted(selected)}

            def compute_selection():
                nonlocal full_hit
                full, full_hit = _cached_payload(cache, "csv", key, compute, checksum)
                return _selected_payload(full, selected)

            payload, hit = _cached_payload(
                cache, "csv_profiles", profile_key, compute_selection, checksum, selected)
            metadata = {
                "hit": hit, "full_hit": full_hit, "key": key,
                "scope": "selected company profiles; aggregates from the entire cleaned CSV",
            }
        payload["preprocessing"]["cache"] = metadata

    if _source_signature(path) != signature:
        raise ValueError("CSV changed while retrieving its processed result; retry with a stable input file")
    payload["source"]["name"] = path.name
    if output is not None:
        write_json(payload, output)
    return payload


def select_company(payload, company_id):
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("dataset_type") != "company_profiles":
        raise ValueError("Unsupported preprocessing JSON format")
    matches = [record for record in payload["companies"] if record["company_id"] == company_id]
    if len(matches) != 1:
        raise ValueError("Expected exactly one matching company in preprocessing JSON")
    return matches[0]
