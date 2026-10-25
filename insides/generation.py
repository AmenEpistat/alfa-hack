"""Model-planned synthesis of multiple events into independent cited articles."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Callable

from .evidence import TOPICS, prepare_input
from .validation import build_insight, parse_and_validate
from .prompts import messages_for, resolve_citation_choices
from .schemas import SynthesisInsightDraft
from .audiences import get_audience
from .products import load_product_catalog
from .synthesis import (
    build_synthesis_catalog,
    build_group_packet,
    planning_messages,
    parse_synthesis_plan,
)

_STOP_CATEGORIES = {
    "budget_exceeded", "authentication", "access_denied", "configuration",
    "response_timeout", "transport", "provider_http", "connection", "call_limit",
    "local_budget",
}


def _safe_error(exc: Exception) -> dict:
    if hasattr(exc, "as_dict"):
        return exc.as_dict()
    if isinstance(exc, ValueError):
        return {"category": "validation", "message": str(exc)[:1500]}
    return {"category": type(exc).__name__, "message": "Generation client failed; no raw request or response logged"}


def _signature(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


def _restore_plan(saved: dict, catalog: dict) -> dict:
    """Revalidate saved event references against this exact bounded catalog."""
    if not isinstance(saved, dict) or set(saved) != {"groups"} or not isinstance(saved["groups"], list):
        raise ValueError("Cannot resume: saved synthesis plan is malformed")
    choices = {
        (str(ref["evidence_id"]), str(ref["quote"])): quote_id
        for quote_id, ref in catalog["choices"].items()
    }
    raw_groups = []
    for group in saved.get("groups", []):
        events = []
        for event in group["events"]:
            refs = []
            for ref in event["evidence"]:
                key = (str(ref["evidence_id"]), str(ref["quote"]))
                if key not in choices:
                    raise ValueError("Cannot resume: a saved planning quote is absent from the current catalog")
                refs.append({"quote_id": choices[key]})
            events.append({"text": event["text"], "evidence": refs})
        raw_groups.append({"title": group["title"], "angle": group["angle"], "events": events})
    return parse_synthesis_plan(json.dumps({"groups": raw_groups}), catalog)


def _resume_state(previous_result, output):
    previous_by_group = {}
    history = []
    saved_plan = None
    if previous_result is not None:
        if previous_result.get("input_canonical_sha256") != output["input_canonical_sha256"]:
            raise ValueError("Cannot resume: ranked input fingerprint has changed")
        if (previous_result.get("target_audience") != output["target_audience"]
                or previous_result.get("product_catalog", {}).get("content_sha256") != output["product_catalog"]["content_sha256"]):
            raise ValueError("Cannot resume: audience or product catalog has changed")
        old_policy = previous_result.get("generation_policy", {})
        if old_policy.get("count_mode") != "model_event_synthesis":
            raise ValueError("Cannot resume: existing result is not a multi-event synthesis run")
        saved_plan = old_policy.get("synthesis_plan")
        for insight in previous_result.get("insights", []):
            group_id = insight.get("synthesis_group_id")
            if not group_id or group_id in previous_by_group:
                raise ValueError("Cannot resume: missing or duplicate synthesis group identity")
            previous_by_group[group_id] = insight
        old_usage = copy.deepcopy(previous_result.get("usage", {}))
        history = old_usage.pop("runs", [])
        if not history:
            history = [{"run_id": previous_result.get("run_id"), **old_usage}]

    return saved_plan, previous_by_group, history


def _update_report(output, current, history, max_repairs):
    policy = output["generation_policy"]
    min_insights = policy["required_min_insights"]
    current = copy.deepcopy(current)
    if history:
        runs = [*history, {"run_id": output["run_id"], **current}]
        combined = copy.deepcopy(current)
        for key in ("input_tokens", "output_tokens", "calls", "submitted_calls"):
            combined[key] = sum((run.get(key) or 0) for run in runs)
        costs = [run.get("cost_rub") for run in runs]
        combined["cost_rub"] = sum(costs) if all(isinstance(value, (float, int)) for value in costs) else None
        combined["usage_estimated"] = any(run.get("usage_estimated", False) for run in runs)
        combined["runs"] = runs
        combined["scope"] = "insides synthesis including planning and resumed calls; other key users excluded"
        output["usage"] = combined
    else:
        output["usage"] = current
    output["self_check"] = {
        "scope": "mechanical structure and provenance; not independent semantic fact-checking",
        "checked_insights_count": len(output["insights"]),
        "completeness": {
            "required_insights": min_insights, "accepted_insights": len(output["insights"]),
            "minimum_met": len(output["insights"]) >= min_insights,
            "required_products_per_insight": 1,
            "all_accepted_have_products": bool(output["insights"]) and all(i["product_recommendations"] for i in output["insights"]),
        },
        "grounding": {
            "exact_quotes_checked": True, "company_fields_checked": True,
            "bank_attribution_checked": True, "product_catalog_quotes_checked": True,
        },
        "consistency": {
            "source_identity_and_text_checked": True, "duplicate_conclusions_checked": True,
            "requested_audience_checked": True,
            "full_semantic_contradiction_check": False,
            "product_suitability_independently_verified": False,
        },
        "correction": {
            "max_repairs_per_response": max_repairs,
            "planning_repair_calls": policy.get("planning_repair_calls", 0),
            "article_repair_calls": sum(i["validation"].get("repair_calls", 0) for i in output["insights"])
                + sum(e.get("repair_calls", 0) for e in output["errors"] if e.get("stage") == "synthesis_generation"),
            "automatic_research_from_generation": False,
        },
        "rejected_or_failed_steps": len(output["errors"]),
        "input_warnings_count": len(output["input_warnings"]),
        "accepted_with_source_warnings": sum(bool(i["warnings"]) for i in output["insights"]),
    }
    policy["generated_insights"] = len(output["insights"])
    policy["minimum_insights_met"] = len(output["insights"]) >= min_insights
    policy["insight_shortfall"] = max(0, min_insights - len(output["insights"]))
    policy["generated_insights_by_topic"] = {
        topic: sum(item["primary_topic"] == topic for item in output["insights"]) for topic in TOPICS
    }
    policy["generated_source_document_ids"] = list(dict.fromkeys(
        doc["document_id"] for insight in output["insights"] for doc in insight["foundation"]["documents"]
    ))


def _new_result(prepared, payload, audience, product_catalog, document_ids, previous_result):
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "schema_version": "1.0", "run_id": str(uuid.uuid4()),
        "input_run_id": prepared["input_run_id"],
        "input_canonical_sha256": fingerprint,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "running", "company_input": copy.deepcopy(prepared["company"]),
        "target_audience": copy.deepcopy(audience),
        "product_catalog": copy.deepcopy(product_catalog),
        "self_check": {},
        "input_status": payload.get("status"), "input_already_ranked": True,
        "generation_policy": {
            "count_mode": "model_event_synthesis",
            "audience_type": audience["type"],
            "minimum_products_per_insight": 1,
            "product_catalog_sha256": product_catalog["content_sha256"],
            "available_unique_documents": len(document_ids),
            "source_documents_by_topic": {
                topic: len(prepared["document_order"].get(topic, [])) for topic in TOPICS
            },
            "count_selected_by": "model",
            "minimum_insights_met": False,
            "planned_insights": None,
            "planning_attempts": 0, "planning_repair_calls": 0,
            "synthesis_plan": None,
            "catalog_coverage": {},
            "selected_source_document_ids": [],
            "generated_source_document_ids": [],
            "all_input_documents_selected": False,
            # Bounded excerpts never establish that all full documents were read.
            "all_input_documents_analyzed": False,
            "stage": "catalog",
        },
        "insights": [], "errors": [], "input_warnings": copy.deepcopy(prepared["warnings"]),
        "limitations": [
            "Exact citations establish traceability, not independent source truth or semantic entailment.",
            "Cross-event linkage and potential company effects are model inferences.",
            "Only the bounded catalog and selected group excerpts are supplied to the model.",
        ],
        "usage": {},
        "recovery": ({
            "previous_run_id": previous_result.get("run_id"),
            "previous_errors": copy.deepcopy(previous_result.get("errors", [])),
            "reused_group_ids": [], "rejected_previous_insights": [],
            "plan_reused": False,
        } if previous_result is not None else None),
    }

def _plan_groups(client, catalog, output, saved_plan, max_repairs):
    policy = output["generation_policy"]
    min_insights = policy["required_min_insights"]
    if len(policy["catalog_document_ids"]) < 2:
        plan = {"groups": []}
        policy["planner_skipped"] = "fewer_than_two_distinct_documents_in_catalog"
    elif saved_plan is not None:
        plan = _restore_plan(saved_plan, catalog)
        output["recovery"]["plan_reused"] = True
    else:
        messages = planning_messages(catalog, output["company_input"], min_insights=min_insights,
                                     target_audience=output["target_audience"], product_catalog=output["product_catalog"])
        policy["planning_attempts"] += 1
        raw = client.complete(messages)
        while True:
            try:
                plan = parse_synthesis_plan(raw, catalog)
                if len(plan["groups"]) < min_insights and policy["planning_repair_calls"] < max_repairs:
                    raise ValueError(
                        f"Plan has {len(plan['groups'])} supported groups; at least {min_insights} distinct insights are required. "
                        "Add genuinely supported combinations without fabricated facts or duplicate conclusions."
                    )
                break
            except ValueError as exc:
                if policy["planning_repair_calls"] >= max_repairs:
                    raise
                policy["planning_repair_calls"] += 1
                messages = [*messages, {"role": "assistant", "content": raw[:32000]}, {
                    "role": "user",
                    "content": "Correct only the plan schema/citation errors and return the complete JSON. Error: " + str(exc)[:1500],
                }]
                policy["planning_attempts"] += 1
                raw = client.complete(messages)
    return plan


def generate_insights(
    payload: dict, client, *, audience_type: str, product_catalog: dict | None = None, min_insights: int = 5,
    max_chars_per_packet: int = 14000, max_catalog_chars: int = 30000,
    max_repairs: int = 1, on_progress: Callable[[dict], None] | None = None,
    previous_result: dict | None = None,
) -> dict:
    """Plan meaningful event combinations, then generate a separate article per group."""
    if isinstance(min_insights, bool) or not isinstance(min_insights, int) or min_insights < 5:
        raise ValueError("min_insights must be an integer >= 5")
    if isinstance(max_repairs, bool) or max_repairs not in (0, 1):
        raise ValueError("max_repairs must be 0 or 1")
    for value, name in ((max_chars_per_packet, "max_chars_per_packet"), (max_catalog_chars, "max_catalog_chars")):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    audience = get_audience(audience_type)
    product_catalog = copy.deepcopy(product_catalog if product_catalog is not None else load_product_catalog())
    if payload.get("target_audience") not in (None, audience):
        raise ValueError("Ranked input targets a different reader audience")
    prepared = prepare_input(payload)
    document_ids = list(dict.fromkeys(record["document_id"] for record in prepared["evidence"].values()))
    configure = getattr(client, "configure_generation_plan", None)
    if callable(configure):
        configure(1, max_repairs)

    output = _new_result(prepared, payload, audience, product_catalog, document_ids, previous_result)
    policy = output["generation_policy"]
    policy.update(
        required_min_insights=min_insights, insight_shortfall=min_insights,
        max_catalog_chars=max_catalog_chars, max_source_chars_per_insight=max_chars_per_packet,
    )
    saved_plan, previous_by_group, history = _resume_state(previous_result, output)

    def publish():
        _update_report(output, getattr(client, "usage", {}), history, max_repairs)
        if on_progress:
            on_progress(copy.deepcopy(output))

    publish()
    try:
        catalog = build_synthesis_catalog(prepared, max_chars=max_catalog_chars)
        policy["catalog_coverage"] = copy.deepcopy(catalog.get("coverage", {}))
        catalog_ids = list(dict.fromkeys(doc["document_id"] for doc in catalog.get("documents", [])))
        policy["catalog_document_ids"] = catalog_ids
        policy["stage"] = "planning"
        publish()
        plan = _plan_groups(client, catalog, output, saved_plan, max_repairs)
        policy["synthesis_plan"] = copy.deepcopy(plan)
        groups = plan["groups"]
        policy["planned_insights"] = len(groups)
        policy["minimum_plan_met"] = len(groups) >= min_insights
        policy["selected_source_document_ids"] = list(dict.fromkeys(
            doc_id for group in groups for doc_id in group["source_document_ids"]
        ))
        policy["all_input_documents_selected"] = bool(document_ids) and (
            set(policy["selected_source_document_ids"]) == set(document_ids)
        )
        policy["unused_source_document_ids"] = [
            doc_id for doc_id in document_ids if doc_id not in policy["selected_source_document_ids"]
        ]
        policy["stage"] = "generating"
        if callable(configure):
            # Includes the planning stage, optional plan repair, and article repairs.
            configure(max(1, len(groups) + 1), max_repairs)
        publish()
    except Exception as exc:
        output["errors"].append({"stage": "synthesis_planning", **_safe_error(exc)})
        output["status"] = "failed"
        policy["stage"] = "failed"
        publish()
        return output

    emitted_signatures = set()
    for index, group in enumerate(groups):
        repair_count = 0
        try:
            packet = build_group_packet(prepared, group, max_chars=max_chars_per_packet)
            packet["company_analysis_context"] = prepared["company_analysis_context"]
            packet["target_audience"] = copy.deepcopy(audience)
            packet["product_catalog"] = copy.deepcopy(product_catalog)
            previous = previous_by_group.get(group["group_id"])
            draft = None
            if previous is not None:
                try:
                    candidate = {field: copy.deepcopy(previous[field]) for field in SynthesisInsightDraft.model_fields if field in previous}
                    for recommendation in candidate.get("product_recommendations", []):
                        recommendation.pop("product", None)
                    draft = parse_and_validate(json.dumps(candidate, ensure_ascii=False), packet)
                except (ValueError, KeyError) as exc:
                    output["recovery"]["rejected_previous_insights"].append({
                        "group_id": group["group_id"], "reason": str(exc)[:1500],
                    })
                else:
                    output["recovery"]["reused_group_ids"].append(group["group_id"])
            if draft is None:
                messages = messages_for(packet)
                raw = client.complete(messages)
                while True:
                    try:
                        draft = parse_and_validate(resolve_citation_choices(raw, packet), packet)
                        break
                    except ValueError as exc:
                        if repair_count >= max_repairs:
                            raise
                        repair_count += 1
                        messages = [*messages, {"role": "assistant", "content": raw[:32000]}, {
                            "role": "user",
                            "content": "Correct only schema/citation errors and return the full synthesis JSON. Error: " + str(exc)[:1500],
                        }]
                        raw = client.complete(messages)
            signature = _signature(draft.synthesis.text)
            if signature in emitted_signatures:
                raise ValueError("Repeated synthesized insight: identical cross-event conclusion already emitted")
            insight = build_insight(draft, prepared, packet, index)
            insight["synthesis_group_id"] = group["group_id"]
            if group.get("rank_set_ids"):
                insight["rank_set_ids"] = copy.deepcopy(group["rank_set_ids"])
            insight["validation"]["repair_calls"] = (
                previous.get("validation", {}).get("repair_calls", 0)
                if previous is not None and group["group_id"] in (output.get("recovery") or {}).get("reused_group_ids", [])
                else repair_count
            )
            output["insights"].append(insight)
            emitted_signatures.add(signature)
        except Exception as exc:
            output["errors"].append({
                "stage": "synthesis_generation", "group_id": group["group_id"],
                "source_document_ids": copy.deepcopy(group["source_document_ids"]),
                "repair_calls": repair_count, **_safe_error(exc),
            })
            if getattr(exc, "category", "") in _STOP_CATEGORIES:
                policy["stopped_early"] = True
                publish()
                break
        publish()
    if len(output["insights"]) < min_insights:
        output["errors"].append({
            "stage": "quantity_requirement",
            "category": "minimum_insights_not_met",
            "message": f"At least {min_insights} validated insights are required; accepted {len(output['insights'])}",
            "required": min_insights, "accepted": len(output["insights"]),
            "shortfall": min_insights - len(output["insights"]),
        })
    output["status"] = (
        "completed" if not output["errors"] else "partial" if output["insights"] else "failed"
    )
    if not groups:
        policy["empty_plan_reason"] = "model_did_not_select_a_supported_multi_event_connection"
    policy["stage"] = output["status"]
    publish()
    return output
