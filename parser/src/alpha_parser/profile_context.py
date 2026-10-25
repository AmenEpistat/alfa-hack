"""Use already computed company facts locally, without recalculating features or sending them to search."""
from copy import deepcopy
import math

FEATURE_NOTES = {
    "worker_mid_approx": "Approximation from a workforce category; not actual headcount.",
    "revenue_per_worker": "Uses approximate workforce; revenue period and units are not supplied.",
    "revenue_rank_industry": "Normalized revenue rank within the supplied OKVED-class dataset; not market share.",
    "industry_freq": "Frequency in the supplied dataset; not market share.",
    "industry_client_share": "Client share in the supplied dataset; not market share.",
    "company_share_group_revenue": "Revenue share within the supplied group records; not market share.",
    "region_revenue_share": "Revenue share within the supplied region records; not market share.",
    "group_size": "Companies in the supplied group; not stores or branches of the selected company.",
    "n_regions_in_group": "Regions of group records; not confirmed operating regions of the selected company.",
    "region_company_count": "Company count in the supplied region records; not the complete regional market.",
    "revenue_log": "Precomputed transformation; revenue period and units are not supplied.",
}

EVENT_FACTORS = {
    "store_opening": ("group_size", "n_regions_in_group", "worker_mid_approx", "revenue_rank_industry"),
    "store_closure": ("group_size", "n_regions_in_group", "worker_mid_approx"),
    "store_relocation": ("group_size", "n_regions_in_group", "worker_mid_approx"),
    "pricing": ("revenue_rank_industry", "revenue_per_worker", "company_share_group_revenue"),
    "financial_results": ("revenue_rank_industry", "revenue_log", "company_share_group_revenue"),
    "investment": ("group_size", "n_regions_in_group", "revenue_rank_industry"),
    "logistics": ("group_size", "n_regions_in_group"),
    "assortment": ("revenue_rank_industry", "worker_mid_approx"),
}


def available(value):
    return value is not None and not (isinstance(value, float) and not math.isfinite(value))


def profile_context(profile):
    """A snapshot of input facts with JSON paths for downstream analysis."""
    data = profile.model_dump(mode="json")
    facts = []
    for key in ("industry", "okved_code", "region", "city"):
        if data.get(key):
            facts.append({"field": key, "value": data[key], "scope": "selected_company", "quality": "input_fact"})
    for key, value in data["features"].items():
        if available(value):
            facts.append({"field": "features." + key, "value": deepcopy(value),
                          "scope": "supplied_dataset" if key.startswith(("industry_", "region_", "okved_share_"))
                                  or key in {"revenue_rank_industry", "group_size", "n_regions_in_group",
                                             "company_share_group_revenue"} else "selected_company",
                          "quality": "category_approximation" if key in {"worker_mid_approx", "revenue_per_worker"}
                                    else "precomputed_feature",
                          "note": FEATURE_NOTES.get(key, "Precomputed by preprocessing; preserved without recalculation.")})
    warnings = list(data["warnings"])
    revenue = data["attributes"].get("REVENUE_COMPANY")
    if revenue == 1000:
        warnings.append("Revenue 1000 is an unknown-value placeholder, not usable revenue.")
    elif isinstance(revenue, (int, float)) and not isinstance(revenue, bool) and math.isfinite(revenue) and revenue >= 0:
        facts.append({"field": "attributes.REVENUE_COMPANY", "value": revenue, "scope": "selected_company",
                      "quality": "input_fact", "note": "Revenue period and units are not supplied; no trend is inferred."})
    return {"source": "preprocessing_json", "company_id": profile.company_id,
            "feature_count": len(data["features"]), "facts": facts,
            "warnings": list(dict.fromkeys(warnings)),
            "limitations": [
                "Group regions do not establish the selected company's trading locations.",
                "Dataset shares and revenue ranks are not market shares.",
                "Category estimates are not actual headcount or measured productivity.",
                "No revenue change or causal business effect can be derived from a single undated profile.",
            ]}


def apply_profile_context(run, profile):
    """Add local company context after evidence collection, outside all external calls."""
    from .competitor_news import build_brief
    context = profile_context(profile)
    run["company_analysis_context"] = context
    by_field = {fact["field"]: fact for fact in context["facts"]}
    for event in run.get("competitor_events", []):
        fields = ["industry", "okved_code", "region", "city"]
        fields.extend("features." + key for key in EVENT_FACTORS.get(event["event_type"], ()))
        facts = [deepcopy(by_field[field]) for field in fields if field in by_field]
        reasoning = []
        if profile.okved_code:
            reasoning.append(f"Компания имеет ОКВЭД {profile.okved_code}.")
        if profile.city or profile.region:
            reasoning.append(f"Местоположение в профиле: {profile.city or profile.region}; оно не подтверждает адреса торговых точек.")
        size = profile.features.get("group_size")
        regions = profile.features.get("n_regions_in_group")
        if available(size):
            reasoning.append(f"В группе по данным preprocessing {size} компаний; это не количество магазинов клиента.")
        if available(regions):
            reasoning.append(f"Записи группы охватывают {regions} регионов; географию выбранной компании нужно оценивать отдельно.")
        for hypothesis in event["impact_hypotheses"]:
            hypothesis["company_factors"] = deepcopy(facts)
            hypothesis["company_context_text"] = " ".join(reasoning)
            hypothesis["company_context_source"] = "preprocessing_json"
            hypothesis["company_warnings"] = list(context["warnings"])
        event["company_context_source"] = "preprocessing_json"
    if "competitor_brief" in run:
        run["competitor_brief"] = build_brief(run)
        run["competitor_brief"]["company_analysis_context"] = deepcopy(context)
