"""Validate claims and attach source, company and product references."""
from __future__ import annotations

import copy
import hashlib
import re
from typing import Any

from pydantic import ValidationError

from .evidence import resolve_company_field, parse_model_json
from .categories import get_category
from .audiences import get_audience
from .schemas import SynthesisInsightDraft
from .markdown import render_insight_markdown, render_sources_markdown, _narrative


class GroundingError(ValueError):
    """A literal source qualifier is absent from its cited evidence."""


def _check_literal_grounding(claim: dict, records: dict, company: dict, path: str):
    if any(field.endswith("worker_mid_approx") for field in claim.get("company_fields", [])):
        if re.search(r"(?:штат|численност|сотрудник|работник)", claim["text"], re.IGNORECASE):
            raise GroundingError(f"{path}: worker_mid_approx is a dataset proxy, not actual headcount; remove staffing assertions")
    if re.search(r"\b[3-9]П\d{2}\b", claim["text"]):
        raise GroundingError(f"{path}: invalid half-year label; use only source-supported time periods")
    for clause in re.split(r"[;!?]|\.(?=\s)|,(?=\s)", claim["text"]):
        if "двузнач" not in clause.casefold():
            continue
        metrics = re.findall(
            r"зарплат|выруч|инфляц|"
            r"ставк|кредит|ввп|рентабел",
            clause.casefold(),
        )
        if len(set(metrics)) > 1:
            continue  # Multiple metrics need semantic review, not a global numeric rejection.
        percentages = [float(value.replace(",", ".")) for value in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", clause)]
        for first, second in re.findall(r"(\d+(?:[.,]\d+)?)\s*[-–—]\s*(\d+(?:[.,]\d+)?)\s*%", clause):
            percentages.extend((float(first.replace(",", ".")), float(second.replace(",", "."))))
        if percentages and any(0 <= value < 10 for value in percentages):
            raise GroundingError(f"{path}: a percentage below 10 cannot be described as double-digit for the same metric")
    if claim["basis"] not in {"source_fact", "bank_position"}:
        return
    text = claim["text"].casefold()
    quoted = " ".join(ref["quote"] for ref in claim["evidence"]).casefold()
    for qualifier in ("медиан", "средневзвеш", "median", "weighted average"):
        if qualifier in text and qualifier not in quoted:
            raise GroundingError(f"{path}: statistical qualifier is absent from cited text; remove it or cite explicit evidence")
    sources = quoted + " " + " ".join(
        str(records[ref["evidence_id"]].get("title") or "")
        for ref in claim["evidence"]
    ).casefold()
    for field in ("region", "city"):
        place = str(company.get(field) or "").casefold().strip()
        if place.startswith("г. "):
            place = place[3:]
        if len(place) >= 5 and place in text and place not in sources and field not in claim["company_fields"]:
            raise GroundingError(f"{path}: event geography is absent from cited text; do not infer it from the client location")


def _claims(value: Any, path: str = ""):
    if isinstance(value, dict):
        if {"text", "basis", "evidence", "company_fields"} <= value.keys():
            yield path, value
        else:
            for key, child in value.items():
                yield from _claims(child, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _claims(child, f"{path}[{index}]")


def parse_and_validate(raw: str, packet: dict) -> SynthesisInsightDraft:
    """Validate structure, citations, company paths and attribution."""
    if not packet.get("synthesis_group"):
        raise ValueError("A selected multi-document synthesis group is required")
    try:
        draft = SynthesisInsightDraft.model_validate(parse_model_json(raw))
    except ValidationError as exc:
        problems = [".".join(map(str, err["loc"])) + ": " + err["type"]
                    for err in exc.errors(include_input=False)[:8]]
        raise ValueError("Schema validation failed: " + "; ".join(problems)) from None
    if draft.primary_document_id != packet["primary_document_id"]:
        raise ValueError("primary_document_id must match the assigned document")
    records = {item["evidence_id"]: item for item in packet["evidence"]}
    data = draft.model_dump()
    audience = packet["target_audience"]
    if data["audience_type"] != audience["type"]:
        raise ValueError("audience_type must match the requested target audience")
    _check_products(data, packet)
    claims = _check_claims(data, packet, records)
    _check_summaries(data, records, claims)
    _check_synthesis(data, packet, records)
    _check_bank(data["bank_assessment"])
    return draft


def _check_products(data, packet):
    products = {item["product_id"]: item for item in packet["product_catalog"]["products"]}
    selected_products = set()
    for item in data["product_recommendations"]:
        pid = item["product_id"]
        if pid not in products or pid in selected_products:
            raise ValueError("Select distinct product_id values from the supplied catalog")
        selected_products.add(pid)
        if not _narrative(item["mechanism"]) or not _narrative(item["application"]):
            raise ValueError("Product mechanism and application must render as substantive user-facing text")
        if any(not _narrative(condition) for condition in item["conditions"]):
            raise ValueError("Product conditions must be substantive applicability conditions, not missing-data diagnostics")
        if not item["capability_quote"].strip() or item["capability_quote"] not in products[pid]["description"]:
            raise ValueError("Product capability_quote must be an exact catalog description substring")
        if item["problem"]["basis"] != "model_inference" or not item["problem"]["company_fields"]:
            raise ValueError("Product problem must be a company-specific model inference")


def _check_claims(data, packet, records):
    claims = list(_claims(data))
    claims.sort(key=lambda item: 0 if item[0].startswith("events[") else 1)
    for path, claim in claims:
        if not claim["text"].strip():
            raise ValueError(f"{path}: empty claim")
        for ref in claim["evidence"]:
            source = records.get(ref["evidence_id"])
            if source is None:
                raise ValueError(f"{path}: unknown evidence_id {ref['evidence_id']}")
            if not ref["quote"].strip() or ref["quote"] not in source["text"]:
                raise ValueError(f"{path}: quote is not an exact retained source substring")
            if claim["basis"] == "bank_position" and source["source_type"] != "alpha_pdf":
                raise ValueError(f"{path}: bank_position requires alpha_pdf evidence")
        for field in claim["company_fields"]:
            try:
                resolve_company_field(packet["company"], field)
            except (ValueError, KeyError):
                raise ValueError(f"{path}: unknown or invalid company field {field}") from None
        _check_literal_grounding(claim, records, packet["company"], path)
    return claims


def _check_summaries(data, records, claims):
    body_documents = {records[ref["evidence_id"]]["document_id"]
                      for path, claim in claims if not path.startswith(("lead", "source_summaries"))
                      for ref in claim["evidence"]}
    if data.get("lead"):
        lead = data["lead"]
        if any(records[ref["evidence_id"]]["document_id"] not in body_documents for ref in lead["evidence"]):
            raise ValueError("Lead must use documents already supporting the article")
        if lead["basis"] in {"model_inference", "assumption"} and not lead["company_fields"]:
            raise ValueError("Lead inference requires company_fields")
    summaries = data.get("source_summaries", [])
    summary_documents = set()
    for item in summaries:
        document_id = item["document_id"]
        summary = item["summary"]
        if document_id not in body_documents or document_id in summary_documents:
            raise ValueError("Source summaries must describe distinct documents used by the article")
        summary_documents.add(document_id)
        if summary["basis"] not in {"source_fact", "bank_position"} or summary["company_fields"]:
            raise ValueError("Source descriptions must be source facts without company features")
        if any(records[ref["evidence_id"]]["document_id"] != document_id for ref in summary["evidence"]):
            raise ValueError("Source summary must cite only its own document")
    if summaries and summary_documents != body_documents:
        raise ValueError("Provide a source summary for every document used by the article")


def _check_synthesis(data, packet, records):
    event = data["what_happened"]
    group = packet["synthesis_group"]
    allowed_fact_documents = set(group["source_document_ids"])
    factual = [event["summary"], *event["key_facts"], *event["participants"], *event["causes"],
               *data.get("events", [])]
    if event["timing"]:
        factual.append(event["timing"])
    for claim in factual:
        if claim["basis"] not in {"source_fact", "bank_position"}:
            raise ValueError("Event facts must be source_fact or bank_position")
        if any(records[ref["evidence_id"]]["document_id"] not in allowed_fact_documents
               for ref in claim["evidence"]):
            raise ValueError("Event facts must cite only the primary document or selected synthesis documents")
    if any(claim["basis"] != "assumption" for claim in event["assumptions"]):
        raise ValueError("Event assumptions must be explicitly labeled assumption")
    contextual = [*data["why_important_for_company"],
                  *(item["claim"] for item in data["possible_consequences"]),
                  *(item["rationale"] for item in data["relevant_actions"]),
                  *(item["problem"] for item in data["product_recommendations"])]
    for claim in contextual:
        if claim["basis"] not in {"model_inference", "assumption"}:
            raise ValueError("Company relevance, consequences and action rationale must be inference or assumption")
        if not claim["company_fields"]:
            raise ValueError("Company relevance, consequences and actions require company_fields")
    declared = data["source_document_ids"]
    if len(declared) != len(set(declared)) or set(declared) != allowed_fact_documents:
        raise ValueError("Synthesis source_document_ids must match its selected group")

    def document_ids(claim):
        return {records[ref["evidence_id"]]["document_id"] for ref in claim["evidence"]}
    event_documents = set().union(*(document_ids(claim) for claim in data["events"]))
    if event_documents != allowed_fact_documents:
        raise ValueError("Synthesis events must cover every selected source document")
    event_texts = {claim["text"].casefold().strip().rstrip(".!?") for claim in data["events"]}
    event_quotes = {ref["quote"].strip() for claim in data["events"] for ref in claim["evidence"]}
    if len(event_texts) < 2 or len(event_quotes) < 2:
        raise ValueError("Synthesis requires distinct events, not repeated statements or quotations")
    emitted_refs = {(ref["evidence_id"], ref["quote"])
                    for claim in data["events"] for ref in claim["evidence"]}
    for planned_event in group["events"]:
        selected_refs = {(ref["evidence_id"], ref["quote"])
                         for ref in planned_event["evidence"]}
        if not selected_refs.intersection(emitted_refs):
            raise ValueError("Synthesis events must retain evidence for each event selected during planning")
    synthesis = data["synthesis"]
    if synthesis["basis"] != "model_inference" or not synthesis["company_fields"]:
        raise ValueError("Synthesis must be a company-specific model inference")
    if document_ids(synthesis) != allowed_fact_documents:
        raise ValueError("Synthesis claim must connect evidence from every selected source")


def _check_bank(bank):
    if bank["status"] == "insufficient_evidence":
        if bank["bank_statements"] or bank["model_interpretation"] is not None:
            raise ValueError("insufficient_evidence requires no bank statements or interpretation")
    elif not bank["bank_statements"]:
        raise ValueError("documented_context requires at least one bank statement")
    if any(claim["basis"] != "bank_position" for claim in bank["bank_statements"]):
        raise ValueError("Bank statements must be labeled bank_position")
    if bank["model_interpretation"] is not None:
        interpretation = bank["model_interpretation"]
        if interpretation["basis"] != "model_inference":
            raise ValueError("Bank linkage to this event must be model_inference")
        bank_ids = {ref["evidence_id"] for c in bank["bank_statements"] for ref in c["evidence"]}
        if not bank_ids.intersection(ref["evidence_id"] for ref in interpretation["evidence"]):
            raise ValueError("Bank interpretation must cite at least one stated bank source")


def _foundation(draft: dict, prepared: dict) -> dict:
    documents: dict[str, dict] = {}
    features: dict[str, dict] = {}
    links = []
    notes = {item.get("field"): item
             for item in prepared.get("company_analysis_context", {}).get("facts", [])}
    for path, claim in _claims(draft):
        links.append({
            "claim_path": path, "basis": claim["basis"],
            "evidence_ids": list(dict.fromkeys(ref["evidence_id"] for ref in claim["evidence"])),
            "company_fields": claim["company_fields"],
        })
        for ref in claim["evidence"]:
            record = prepared["evidence"][ref["evidence_id"]]
            key = record["document_id"]
            if key not in documents:
                documents[key] = {
                    "document_id": key, "title": record["title"],
                    "original_filename": record.get("original_filename"),
                    "source_type": record["source_type"], "topics": [],
                    "url": record["url"], "published_at": record["published_at"],
                    "fetched_at": record["fetched_at"], "citations": [],
                }
            doc = documents[key]
            doc["topics"] = list(dict.fromkeys([*doc["topics"], *record["topics"]]))
            start = record["text"].find(ref["quote"])
            citation = {
                "evidence_id": ref["evidence_id"],
                "version_id": record["version_id"], "chunk_id": record["chunk_id"],
                "quote": ref["quote"],
                "page_start": record["page_start"], "page_end": record["page_end"],
                "chunk_char_start": record["char_start"], "chunk_char_end": record["char_end"],
                "quote_start_in_chunk": start, "quote_end_in_chunk": start + len(ref["quote"]),
                "chunk_text_sha256": hashlib.sha256(record["text"].encode()).hexdigest(),
                "quality": record["quality"], "warnings": record["warnings"],
            }
            if citation not in doc["citations"]:
                doc["citations"].append(citation)
        for field in claim["company_fields"]:
            feature = copy.deepcopy(notes.get(field, {"field": field, "scope": "input_profile"}))
            feature["value"] = resolve_company_field(prepared["company"], field)
            features[field] = feature
    return {"documents": list(documents.values()),
            "company_features": list(features.values()), "claim_links": links}


def build_insight(draft: SynthesisInsightDraft, prepared: dict, packet: dict, index: int) -> dict:
    data = draft.model_dump(mode="json")
    foundation = _foundation(data, prepared)
    products = {item["product_id"]: item for item in packet["product_catalog"]["products"]}
    for recommendation in data["product_recommendations"]:
        recommendation["product"] = copy.deepcopy(products[recommendation["product_id"]])
    warnings = []
    for document in foundation["documents"]:
        if not document["published_at"]:
            warnings.append(f"Дата публикации не подтверждена: {document['title']}")
        for citation in document["citations"]:
            if citation["quality"] not in {"extracted", "verified"}:
                warnings.append(f"Требуется проверка извлечённого текста: {document['title']}")
            warnings.extend(citation["warnings"])
    if any(item.get("text_truncated") for item in packet["evidence"]):
        warnings.append("Модели передана ограниченная выдержка; весь документ не анализировался.")
    digest = hashlib.sha256(
        f"{prepared['input_run_id']}:{packet['synthesis_group']['group_id']}".encode()
    ).hexdigest()[:16]
    result = {
        "insight_id": "ins_" + digest, "generation_order": index + 1,
        "primary_topic": packet["primary_topic"],
        "input_document_rank": packet.get("input_rank"),
        **data, "target_audience": get_audience(data["audience_type"]),
        "category": get_category(data["category_id"]), "foundation": foundation,
        "evidence_status": "requires_review" if warnings else "traceable",
        "warnings": list(dict.fromkeys(warnings)),
        "validation": {
            "six_blocks_present": True, "exact_quotes_checked": True,
            "source_ids_checked": True, "company_fields_checked": True,
            "bank_attribution_checked": True,
            "semantic_entailment_automatically_verified": False,
            "business_category_checked": True,
            "requested_audience_checked": True,
            "audience_semantic_alignment_automatically_verified": False,
            "minimum_one_product_checked": True,
            "product_ids_and_capability_quotes_checked": True,
            "product_suitability_automatically_verified": False,
        },
    }
    if packet.get("synthesis_group"):
        result["synthesis_group_id"] = packet["synthesis_group"]["group_id"]
        result["source_document_ids"] = list(packet["synthesis_group"]["source_document_ids"])
        result["topics"] = list(dict.fromkeys(
            topic for document in foundation["documents"] for topic in document.get("topics", [])
        ))
        result["validation"]["multiple_events_checked"] = True
        result["validation"]["cross_source_synthesis_checked"] = True
    result["markdown"] = render_insight_markdown(result)
    result["sources_markdown"] = render_sources_markdown(result)
    return result




