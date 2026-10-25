"""Deterministic PDF extraction. OCR is always unverified evidence."""
import json
from pathlib import Path
import pymupdf
from .config import Settings
from .schemas import Chunk, Document, utcnow
from .storage import Store, digest

from .pdf_cache import (CACHE_SCHEMA, EXTRACTOR, cacheable_extraction,
                        extraction_from_document, pdf_cache_key, pdf_signature,
                        signature_hash, valid_extraction, seed_pdf_cache as seed_pdf_cache)


def pieces(text: str, size=1600):
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind("\n", start + size // 2, end)
            if boundary > start:
                end = boundary + 1
        yield start, end, text[start:end]
        start = end


def read_blocks(page, warnings, page_number):
    blocks = [b for b in page.get_text("blocks", sort=True) if b[6] == 0 and b[4].strip()]
    # Detect a central gutter; don't interleave independent columns by y coordinate.
    width = page.rect.width
    left = [b for b in blocks if b[2] < width * .57 and b[0] < width * .4]
    right = [b for b in blocks if b[0] > width * .43]
    if len(left) >= 3 and len(right) >= 3:
        warnings.append(f"page {page_number}: multi-column layout; reading order needs review")
        span = [b for b in blocks if b not in left and b not in right]
        top = min(min(b[1] for b in left), min(b[1] for b in right))
        blocks = sorted([b for b in span if b[1] < top], key=lambda b: b[1]) + sorted(left, key=lambda b: b[1]) + sorted(right, key=lambda b: b[1]) + sorted([b for b in span if b[1] >= top], key=lambda b: b[1])
    return blocks


class _UncacheableExtraction(Exception):
    def __init__(self, payload):
        self.payload = payload


def _extract_pdf(content, sha, settings):
    warnings, chunks, pages, tables = [], [], [], []
    metadata = {}
    try:
        with pymupdf.open(stream=content, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise ValueError("encrypted PDF; credentials not provided")
            metadata = pdf.metadata or {}
            for i, original_page in enumerate(pdf):
                number = i + 1
                page = original_page
                ocr_doc = None
                used_ocr = False
                if len(page.get_text().strip()) < 50:
                    if settings.ocr_enabled:
                        try:
                            pix = page.get_pixmap(dpi=settings.ocr_dpi)
                            ocr_data = pix.pdfocr_tobytes(language=settings.ocr_language, tessdata=str(settings.tessdata.resolve()))
                            ocr_doc = pymupdf.open(stream=ocr_data, filetype="pdf")
                            page = ocr_doc[0]
                            used_ocr = True
                            warnings.append(f"page {number}: OCR; numbers, charts and tables require visual verification")
                        except Exception as exc:
                            warnings.append(f"page {number}: OCR unavailable ({type(exc).__name__})")
                    else:
                        warnings.append(f"page {number}: no text layer; OCR disabled")
                blocks = read_blocks(page, warnings, number)
                text = "\n".join(b[4] for b in blocks)
                if len(text.strip()) < 100:
                    warnings.append(f"page {number}: empty or sparse extraction")
                if text.count("\ufffd") / max(len(text), 1) > .01:
                    warnings.append(f"page {number}: broken character mapping")
                page_tables = []
                try:
                    detected = page.find_tables(strategy="text" if used_ocr else "lines")
                    for j, table in enumerate(detected.tables):
                        rows = table.extract()
                        if table.col_count < 2 or table.row_count < 2:
                            continue
                        id_ = f"{sha[:16]}-p{number}-t{j}"
                        # Surrounding text retains original units/labels without inventing them.
                        header_context = page.get_textbox(pymupdf.Rect(0, max(0, table.bbox[1] - 70), page.rect.width, table.bbox[1]))
                        table_data = {"table_id": id_, "page": number, "bbox": list(table.bbox),
                                      "headers": table.header.names, "rows": rows,
                                      "units": None, "header_context": header_context,
                                      "quality": "requires_review" if used_ocr else "extracted",
                                      "warning": "OCR grid candidate, may include prose" if used_ocr else None}
                        tables.append(table_data)
                        page_tables.append(id_)
                        table_text = json.dumps({"headers": table.header.names, "rows": rows, "context": header_context}, ensure_ascii=False)
                        chunks.append(Chunk(text=table_text, page_start=number, page_end=number,
                                            section_title="table candidate" if used_ocr else "table", table_ids=[id_]))
                except Exception as exc:
                    warnings.append(f"page {number}: table extraction failed ({type(exc).__name__})")
                pages.append({"page": number, "text": text, "ocr": used_ocr,
                              "blocks": [{"bbox": list(b[:4]), "text": b[4]} for b in blocks],
                              "width": page.rect.width, "height": page.rect.height})
                for _, _, part in pieces(text):
                    if part.strip():
                        chunks.append(Chunk(text=part, page_start=number, page_end=number, table_ids=page_tables))
                if ocr_doc:
                    ocr_doc.close()
    except Exception as exc:
        warnings.append(f"PDF extraction failed: {type(exc).__name__}: {str(exc)[:150]}")
    quality = "extracted" if not warnings else "requires_review"
    if not any(p["text"].strip() for p in pages):
        quality = "failed"
    return {
        "schema": CACHE_SCHEMA, "content_sha256": sha,
        "metadata": metadata, "quality": quality, "warnings": warnings,
        "pages": pages, "tables": tables,
        "chunks": [chunk.model_dump(mode="json", exclude={"chunk_id", "document_id", "version_id"})
                   for chunk in chunks],
        "extracted_at": utcnow(), "provenance": "pdf_extraction",
        "ocr_model_provenance": "recorded_config",
    }


def _save_extraction(store, path, content, payload, signature, *, logical_id,
                     title, published_at, force):
    metadata = payload["metadata"]
    doc = Document(
        source_type="alpha_pdf", source_name="Альфа-Банк / предоставленный аналитический корпус",
        original_filename=path.name, title=title or metadata.get("title") or path.stem,
        author=metadata.get("author") or None, published_at=published_at,
        content_hash=payload["content_sha256"], config_hash=signature_hash(signature),
        extractor_version=EXTRACTOR, quality=payload["quality"],
        warnings=payload["warnings"], original_path=store.original(content, ".pdf"),
        tables=payload["tables"], pages=payload["pages"],
        **({"fetched_at": payload["extracted_at"]} if payload.get("extracted_at") else {}),
    )
    chunks = [Chunk.model_validate(chunk) for chunk in payload["chunks"]]
    # CreationDate is deliberately not treated as publication date.
    return store.save_document("alpha:" + (logical_id or path.name), doc, chunks, force=force)


def parse_pdf(store: Store, settings: Settings, path: Path, *, logical_id=None,
              title=None, published_at=None, force=False, cached_only=False) -> dict:
    """Reuse extracted content across run folders; apply this request's metadata."""
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        raise ValueError("PDF required")
    if force and cached_only:
        raise ValueError("force cannot be combined with cached_only")
    # Hash the exact immutable byte snapshot which will be extracted and retained.
    content = path.read_bytes()
    sha = digest(content)
    signature = pdf_signature(settings)
    key = pdf_cache_key(sha, signature)
    cache = getattr(store, "cache", None)
    payload, hit, scope = None, False, "none"

    def compute():
        extracted = _extract_pdf(content, sha, settings)
        if pdf_signature(settings) != signature:
            raise ValueError("OCR models or extraction configuration changed during PDF processing")
        extracted["signature"] = signature
        if not cacheable_extraction(extracted):
            # A failed extraction is still returned to the caller and recorded
            # with its real quality; it must never become a permanent cache hit.
            raise _UncacheableExtraction(extracted)
        return extracted

    if not force and cache is not None:
        candidate = cache.get("pdf", key)
        if valid_extraction(candidate, sha, signature):
            payload, hit, scope = candidate, True, "shared"
        elif candidate is not None:
            cache.invalidate("pdf", key)
    if payload is None and not force:
        prior = store.processed(sha, EXTRACTOR, signature_hash(signature))
        if prior is not None:
            payload = extraction_from_document(prior, store.chunks(prior["version_id"]), signature)
            if cacheable_extraction(payload):
                hit, scope = True, "run"
                if cache is not None:
                    cache.put("pdf", key, payload)
            else:
                payload = None
    if payload is None:
        if cached_only:
            raise ValueError("PDF extraction cache miss for the current file, code and OCR configuration")
        try:
            if cache is None or force:
                payload = compute()
                if cache is not None:
                    cache.put("pdf", key, payload)
            else:
                payload, hit = cache.get_or_compute("pdf", key, compute)
                scope = "shared" if hit else "none"
                if not valid_extraction(payload, sha, signature):
                    cache.invalidate("pdf", key)
                    raise ValueError("PDF extraction cache contains an invalid entry; retry processing")
        except _UncacheableExtraction as failed:
            payload = failed.payload
    result = _save_extraction(
        store, path, content, payload, signature, logical_id=logical_id, title=title,
        published_at=published_at, force=force)
    result["cache"] = {"hit": hit, "scope": scope, "key": key,
                       "provenance": payload.get("provenance"),
                       "ocr_model_provenance": payload.get("ocr_model_provenance")}
    return result


def ingest_manifest(store, settings, manifest: Path, force=False):
    spec = json.loads(Path(manifest).read_text(encoding="utf-8"))
    results = []
    for entry in spec["documents"]:
        try:
            path = settings.input_dir / "analytics" / entry["file"]
            result = parse_pdf(store, settings, path, logical_id=entry["logical_id"],
                               title=entry.get("title"), published_at=entry.get("published_at"), force=force)
            results.append(result)
        except Exception as exc:
            results.append({"file": entry["file"], "error": f"{type(exc).__name__}: {exc}", "quality": "failed"})
    return results
