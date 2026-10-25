"""Restore ranked sources from parser JSON without losing citation metadata."""
from __future__ import annotations

import copy
import hashlib


def ranked_for_insights(source: dict, ranking_result: dict) -> dict:
    from insides.evidence import TOPICS, prepare_input

    prepare_input(source)
    if ranking_result.get("run_id") != source.get("run_id"):
        raise ValueError("Ranking result belongs to another parser run")
    if ranking_result.get("status") not in {"ok", "completed", "partial"}:
        raise ValueError("Ranking did not return a usable result")
    sets = ranking_result.get("sets")
    if not isinstance(sets, list):
        raise ValueError("Ranking result must contain sets[]")

    available = {}
    for topic in TOPICS:
        for row in source["topics"].get(topic, []):
            item_id = row.get("item_id")
            if not isinstance(item_id, str) or not item_id:
                raise ValueError("Parser source must have item_id")
            if item_id in available and available[item_id][1] != row:
                raise ValueError("Conflicting parser item_id: " + item_id)
            available[item_id] = (topic, row)

    ranked = copy.deepcopy(source)
    ranked["topics"] = {topic: [] for topic in TOPICS}
    ranked["ranking_sets"] = []
    ranked["ranking_diagnostics"] = copy.deepcopy(ranking_result.get("diagnostics", {}))
    ranked["status"] = "completed" if source.get("status") == "completed" and ranking_result["status"] != "partial" else "partial"
    selected, set_ids = set(), set()
    for group in sets:
        set_id = group.get("set_id")
        if not isinstance(set_id, str) or not set_id or set_id in set_ids:
            raise ValueError("Ranking set_id must be non-empty and unique")
        set_ids.add(set_id)
        if not isinstance(group.get("company"), dict):
            raise ValueError("Ranking set must identify its subject company")
        entry = {key: copy.deepcopy(group.get(key)) for key in ("set_id", "company", "set_score", "warnings")}
        entry.update(evidence_ids=[], news_evidence_ids=[], analytics_evidence_ids=[])
        for field, is_pdf in (("news", False), ("analytics", True)):
            items = group.get(field)
            if not isinstance(items, list) or not items:
                raise ValueError("Ranking set needs news and analytics")
            for item in items:
                item_id = item.get("item_id")
                if item_id not in available:
                    raise ValueError("Ranker selected an unknown item_id: " + str(item_id))
                topic, original = available[item_id]
                if (topic == "pdf") != is_pdf:
                    raise ValueError("Ranker changed the source category")
                for key in ("document_id", "version_id", "chunk_id", "title", "text", "url", "published_at", "page_start", "page_end"):
                    if key in item and item[key] != original.get(key):
                        raise ValueError("Ranker changed source " + key + ": " + item_id)
                evidence_id = "ev_" + hashlib.sha256(
                    f"{original['version_id']}:{original['chunk_id']}".encode("utf-8")
                ).hexdigest()[:16]
                for key in ("evidence_ids", "analytics_evidence_ids" if is_pdf else "news_evidence_ids"):
                    if evidence_id not in entry[key]:
                        entry[key].append(evidence_id)
                if item_id not in selected:
                    row = copy.deepcopy(original)
                    row["ranking"] = {"score": item.get("score"), "provenance": copy.deepcopy(item.get("provenance", []))}
                    ranked["topics"][topic].append(row)
                    selected.add(item_id)
        ranked["ranking_sets"].append(entry)
    prepare_input(ranked)
    return ranked
