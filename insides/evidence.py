"""Build source-grounded model packets from already ranked parser JSON."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import defaultdict
from typing import Any

TOPICS = ("news", "pdf", "competitors")
IDENTITY_FIELDS = ("document_id", "version_id", "chunk_id")
RECORD_FIELDS = (
    "document_id", "version_id", "chunk_id", "title", "text", "source_type",
    "source_name", "original_filename", "url", "published_at", "publication_date_evidence",
    "fetched_at", "page_start", "page_end", "char_start", "char_end",
    "section_title", "table_ids", "quality", "warnings", "entity_matches",
)
_PATH = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")


def _unique_append(values: list, value: Any) -> None:
    if value not in values:
        values.append(value)


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [json.dumps(value, ensure_ascii=False, sort_keys=True)]


def _position(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer or null")
    return value


def prepare_input(payload: dict) -> dict:
    """Return a lossless, deduplicated evidence catalog in supplied topic order."""
    if not isinstance(payload, dict):
        raise ValueError("Ranked input must be an object")
    company = payload.get("company_input")
    if not isinstance(company, dict) or not company:
        raise ValueError("company_input must contain the full preprocessed company object")
    topics = payload.get("topics")
    if not isinstance(topics, dict):
        raise ValueError("topics must be an object containing ranked source lists")

    warnings: list[str] = []
    status = payload.get("status")
    if status and status != "completed":
        warnings.append(f"Input parser status: {status}; source limitations remain applicable")
    for field in ("warnings", "gaps"):
        for message in _strings(payload.get(field)):
            _unique_append(warnings, message)
    for topic, messages in (payload.get("topic_gaps") or {}).items():
        for message in _strings(messages):
            _unique_append(warnings, f"{topic}: {message}")
    for error in payload.get("errors") or []:
        _unique_append(
            warnings,
            "Input source error: " + json.dumps(error, ensure_ascii=False, sort_keys=True),
        )
    for message in _strings(company.get("warnings")):
        _unique_append(warnings, f"Company input: {message}")

    evidence: dict[str, dict] = {}
    document_order: dict[str, list[str]] = {topic: [] for topic in TOPICS}
    version_documents: dict[str, str] = {}
    document_versions: dict[str, list[str]] = defaultdict(list)
    for topic in TOPICS:
        rows = topics.get(topic, [])
        if not isinstance(rows, list):
            raise ValueError(f"topics.{topic} must be a list")
        if not rows:
            _unique_append(warnings, f"No ranked documents supplied for topic: {topic}")
        for index, row in enumerate(rows):
            prefix = f"topics.{topic}[{index}]"
            if not isinstance(row, dict):
                raise ValueError(f"{prefix} must be an object")
            for field in IDENTITY_FIELDS:
                if not isinstance(row.get(field), str) or not row[field].strip():
                    raise ValueError(f"{prefix}.{field} must be a non-empty string")
            if not isinstance(row.get("text"), str) or not row["text"].strip():
                raise ValueError(f"{prefix}.text must contain non-empty source text")
            if not isinstance(row.get("source_type"), str) or not row["source_type"].strip():
                raise ValueError(f"{prefix}.source_type must be a non-empty string")
            doc_id, version_id, chunk_id = (row[field] for field in IDENTITY_FIELDS)
            previous_doc = version_documents.setdefault(version_id, doc_id)
            if previous_doc != doc_id:
                raise ValueError(f"Version {version_id} belongs to conflicting documents")
            _unique_append(document_versions[doc_id], version_id)
            record = {field: copy.deepcopy(row.get(field)) for field in RECORD_FIELDS}
            record["title"] = row.get("title") or ""
            record["warnings"] = _strings(row.get("warnings"))
            record["quality"] = row.get("quality") or "unknown"
            for field in ("table_ids", "entity_matches"):
                record[field] = copy.deepcopy(row.get(field) or [])
            for start, end in (("page_start", "page_end"), ("char_start", "char_end")):
                record[start] = _position(row.get(start), f"{prefix}.{start}")
                record[end] = _position(row.get(end), f"{prefix}.{end}")
                if record[start] is not None and record[end] is not None:
                    if record[end] < record[start]:
                        raise ValueError(f"{prefix}.{end} precedes {start}")
            evidence_id = "ev_" + hashlib.sha256(
                f"{version_id}:{chunk_id}".encode("utf-8")
            ).hexdigest()[:16]
            record["evidence_id"] = evidence_id
            existing = evidence.get(evidence_id)
            if existing is not None:
                previous = {key: value for key, value in existing.items() if key not in {"topics", "input_ranks"}}
                if previous != record:
                    raise ValueError(
                        f"Conflicting metadata or text for source chunk {version_id}:{chunk_id}"
                    )
                _unique_append(existing["topics"], topic)
                existing["input_ranks"].setdefault(topic, index + 1)
            else:
                record["topics"] = [topic]
                record["input_ranks"] = {topic: index + 1}
                evidence[evidence_id] = record
            _unique_append(document_order[topic], doc_id)

    for doc_id, versions in document_versions.items():
        if len(versions) > 1:
            warnings.append(
                f"Document {doc_id} contains multiple supplied versions, all retained: "
                + ", ".join(versions)
            )
    for record in evidence.values():
        if not record["published_at"]:
            _unique_append(warnings, f"Publication date is unknown for document {record['document_id']}")
        if record["quality"] not in {"extracted", "verified"}:
            _unique_append(
                warnings,
                f"Source quality for document {record['document_id']}: {record['quality']}",
            )
        for warning in record["warnings"]:
            _unique_append(warnings, f"Document {record['document_id']}: {warning}")
    return {
        "company": copy.deepcopy(company),
        "input_run_id": payload.get("run_id"),
        "company_analysis_context": copy.deepcopy(payload.get("company_analysis_context") or {}),
        "evidence": evidence,
        "document_order": document_order,
        "warnings": warnings,
    }


def resolve_company_field(company: dict, path: str) -> Any:
    """Resolve an explicit dotted dictionary path; reject expressions/indexing."""
    if not isinstance(path, str) or not _PATH.fullmatch(path):
        raise ValueError("Company field must be a dotted dictionary path")
    current: Any = company
    for component in path.split("."):
        if component.startswith("__"):
            raise ValueError("Private attributes are not company fields")
        if not isinstance(current, dict) or component not in current:
            raise KeyError(path)
        current = current[component]
    return copy.deepcopy(current)


def _table_text(record: dict) -> bool:
    text = record["text"].lstrip()
    if text.startswith(("{", "[")):
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            data = None
        if isinstance(data, dict) and any(key in data for key in ("headers", "rows", "cells")):
            return True
        if isinstance(data, list):
            return True
    # table_ids also occur on narrative chunks from a page containing a table.
    return record.get("section_title") == "table candidate"


def parse_model_json(raw: str) -> dict:
    if not isinstance(raw, str) or len(raw) > 200000:
        raise ValueError("Model response must be a bounded JSON string")
    stripped = raw.strip()
    fence = chr(96) * 3
    if stripped.startswith(fence) and stripped.endswith(fence):
        lines = stripped.splitlines()
        if lines[0].strip().lower() not in {fence, fence + "json"}:
            raise ValueError("Unsupported code fence")
        stripped = "\n".join(lines[1:-1])
    try:
        value = json.loads(stripped)
    except (ValueError, TypeError):
        raise ValueError("Model response is not a complete JSON object") from None
    if not isinstance(value, dict):
        raise ValueError("Model response must be a JSON object")
    return value
