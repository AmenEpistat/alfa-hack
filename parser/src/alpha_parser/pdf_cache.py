"""Portable extraction cache; caller metadata and run identities stay outside it."""
import copy
import json
import re
from pathlib import Path
import pymupdf
from .cache import code_fingerprint, file_sha256
from .schemas import Chunk
from .storage import digest

EXTRACTOR = f"pymupdf-{pymupdf.VersionBind}/alpha-3"
CACHE_SCHEMA = "pdf-extraction-1"


def legacy_config_hash(settings):
    return digest(json.dumps({"chunk": 1600, "ocr": settings.ocr_enabled,
                              "dpi": settings.ocr_dpi, "lang": settings.ocr_language}))


def pdf_signature(settings):
    """Fingerprint extraction code, every active OCR model and actual settings."""
    models = []
    if settings.ocr_enabled:
        for language in settings.ocr_language.split("+"):
            if not re.fullmatch(r"[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*", language):
                raise ValueError("Invalid OCR language name")
            path = Path(settings.tessdata) / (language + ".traineddata")
            models.append({"language": language,
                           "sha256": file_sha256(path) if path.is_file() else None})
    here = Path(__file__).resolve().parent
    return {"schema": CACHE_SCHEMA, "extractor": EXTRACTOR,
            "code": code_fingerprint([here / "pdf.py", here / "pdf_cache.py", here / "schemas.py"]),
            "chunk_size": 1600, "ocr_enabled": settings.ocr_enabled,
            "ocr_dpi": settings.ocr_dpi, "ocr_language": settings.ocr_language,
            "ocr_models": models}


def signature_hash(signature):
    return digest(json.dumps(signature, sort_keys=True, separators=(",", ":")))


def pdf_cache_key(content_hash, signature):
    return digest(json.dumps({"content_sha256": content_hash, "signature": signature},
                             sort_keys=True, separators=(",", ":")))


def cacheable_extraction(payload):
    return (payload.get("quality") in {"extracted", "requires_review"}
            and bool(payload.get("chunks"))
            and not any("PDF extraction failed:" in warning or "OCR unavailable" in warning
                        for warning in payload.get("warnings", [])))


def valid_extraction(payload, content_hash, signature):
    if not isinstance(payload, dict):
        return False
    if (payload.get("schema") != CACHE_SCHEMA
            or payload.get("content_sha256") != content_hash
            or payload.get("signature") != signature
            or not isinstance(payload.get("chunks"), list)
            or not isinstance(payload.get("warnings"), list)
            or not all(isinstance(warning, str) for warning in payload["warnings"])
            or not cacheable_extraction(payload)):
        return False
    try:
        for chunk in payload["chunks"]:
            Chunk.model_validate(chunk)
    except (ValueError, TypeError):
        return False
    return (isinstance(payload.get("metadata"), dict)
            and isinstance(payload.get("pages"), list)
            and isinstance(payload.get("tables"), list))


def extraction_from_document(document, chunks, signature, *, provenance="run_stage",
                             ocr_model_provenance="recorded_config"):
    """Discard presentation fields and IDs; quote text and layout remain exact."""
    retained = []
    for original in chunks:
        chunk = copy.deepcopy(original)
        for key in ("chunk_id", "document_id", "version_id"):
            chunk.pop(key, None)
        retained.append(chunk)
    return {"schema": CACHE_SCHEMA, "content_sha256": document["content_hash"],
            "signature": copy.deepcopy(signature), "quality": document["quality"],
            "warnings": copy.deepcopy(document.get("warnings", [])),
            "pages": copy.deepcopy(document.get("pages", [])),
            "tables": copy.deepcopy(document.get("tables", [])),
            "chunks": retained,
            # A manifest title may differ from embedded PDF metadata.
            # Old stages do not record that distinction: never reuse their title.
            "metadata": {"title": None, "author": document.get("author")},
            "extracted_at": document.get("fetched_at"),
            "provenance": provenance, "ocr_model_provenance": ocr_model_provenance}


def seed_pdf_cache(store, settings, manifest, *, allow_legacy=False):
    """Import a verified historical extraction without opening or OCRing a PDF.

    Legacy OCR model hashes were not recorded. Their migration requires explicit
    allow_legacy=True and remains marked in each entry's provenance.
    """
    cache = getattr(store, "cache", None)
    if cache is None:
        raise ValueError("A shared JSON cache is required")
    spec = json.loads(Path(manifest).read_text(encoding="utf-8-sig"))
    signature = pdf_signature(settings)
    config_hash = signature_hash(signature)
    legacy_hash = legacy_config_hash(settings)
    report = {"seeded": [], "already_cached": [], "skipped": []}
    for entry in spec["documents"]:
        path = Path(settings.input_dir) / "analytics" / entry["file"]
        if not path.is_file():
            report["skipped"].append({"file": entry["file"], "reason": "input missing"})
            continue
        source_hash = file_sha256(path)
        key = pdf_cache_key(source_hash, signature)
        if valid_extraction(cache.get("pdf", key), source_hash, signature):
            report["already_cached"].append(path.name)
            continue
        matches = [doc for doc in store.documents(history=True)
                   if doc.get("source_type") == "alpha_pdf"
                   and doc.get("content_hash") == source_hash
                   and doc.get("extractor_version") == EXTRACTOR
                   and doc.get("original_filename") == path.name]
        chosen = None
        legacy = False
        for document in reversed(matches):
            if document.get("config_hash") == config_hash:
                chosen = document
                break
            if allow_legacy and document.get("config_hash") == legacy_hash:
                chosen, legacy = document, True
                break
        if chosen is None:
            report["skipped"].append({"file": entry["file"], "reason": "no matching extraction/configuration"})
            continue
        payload = extraction_from_document(
            chosen, store.chunks(chosen["version_id"]), signature,
            provenance="legacy_stage_import" if legacy else "stage_import",
            ocr_model_provenance=("not_recorded_by_legacy_extractor" if legacy and settings.ocr_enabled
                                  else "recorded_config"))
        if not cacheable_extraction(payload):
            report["skipped"].append({"file": entry["file"], "reason": "failed/incomplete extraction"})
            continue
        # Detect a file or OCR-model change while constructing the entry.
        if file_sha256(path) != source_hash or pdf_signature(settings) != signature:
            raise ValueError("PDF or extraction settings changed during cache import")
        cache.put("pdf", key, payload)
        report["seeded"].append({"file": path.name, "key": key,
                                 "provenance": payload["provenance"],
                                 "ocr_model_provenance": payload["ocr_model_provenance"]})
    return report
