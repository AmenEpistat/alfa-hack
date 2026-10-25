"""Build final ranking sets: company + 2-5 news + 1-3 analytics."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .config import AppConfig
from .features import CompanyProfile, build_features, company_profile
from .ranker_analytics import rank_analytics
from .ranker_news import NewsCandidate, rank_news

log = logging.getLogger(__name__)


@dataclass
class RankingSet:
    set_id: str
    company: dict[str, Any]
    news: list[dict[str, Any]]
    analytics: list[dict[str, Any]]
    set_score: float
    warnings: list[str] = field(default_factory=list)


def _company_dict(
    profile: CompanyProfile, watch: Any | None, role: str, score: float
) -> dict[str, Any]:
    return {
        "id": profile.id,
        "name": profile.name or (getattr(watch, "name", None) if watch else None),
        "role": role,
        "relationship": getattr(watch, "relationship", None) if watch else None,
        "origin": getattr(watch, "origin", None) if watch else None,
        "score": float(score),
    }

def _item_type(item: Any) -> str:
    topic = getattr(item, "topic", None)
    if topic == "pdf":
        return "pdf"
    return "news"


def _news_dict(c: NewsCandidate, item: Any) -> dict[str, Any]:
    return {
        "item_id": c.item_id,
        "document_id": getattr(item, "document_id", None),
        "type": _item_type(item),
        "title": getattr(item, "title", None),
        "text": getattr(item, "text", None),
        "url": getattr(item, "url", None),
        "published_at": getattr(item, "published_at", None),
        "date_in_range": getattr(item, "date_in_range", None),
        "score": float(c.score_total),
        "provenance": list(c.provenance),
    }


def _analytics_dict(c, item: Any) -> dict[str, Any]:
    return {
        "item_id": c.item_id,
        "document_id": getattr(item, "document_id", None),
        "type": _item_type(item),
        "title": getattr(item, "title", None),
        "text": getattr(item, "text", None),
        "url": getattr(item, "url", None),
        "published_at": getattr(item, "published_at", None),
        "date_in_range": getattr(item, "date_in_range", None),
        "page_start": getattr(item, "page_start", None),
        "page_end": getattr(item, "page_end", None),
        "score": float(c.score_total),
        "provenance": list(c.provenance),
    }


def build_sets(
    payload: Any,
    companies_df: pd.DataFrame,
    watch_items: list[Any],
    cfg: AppConfig,
) -> list[RankingSet]:
    """Generate 5-10 sets of company + news + analytics."""
    news_pool = list(payload.topics.news) + list(payload.topics.competitors)
    analytics_pool = list(payload.topics.pdf)
    news_by_id = {getattr(n, "item_id", None): n for n in news_pool if getattr(n, "item_id", None)}
    analytics_by_id = {
        getattr(n, "item_id", None): n for n in analytics_pool if getattr(n, "item_id", None)
    }

    df = build_features(companies_df, cfg.features, force=cfg.features.force_recompute)
    rows_by_key = {}
    for idx, row in df.iterrows():
        key = str(row.get("SYNTHETIC_U", idx))
        rows_by_key[key] = row

    # primary companies from watchlist
    profiles: list[tuple[CompanyProfile, Any | None, str]] = []
    for w in watch_items:
        # find matching company row by name or id if possible
        row = rows_by_key.get(w.id)
        if row is None:
            # try name match in a "name" column if exists; else use default empty row
            row = pd.Series(dtype=object)
        profiles.append((company_profile(row, w), w, "primary"))

    # also add top companies from df as competitor candidates (limited)
    competitor_budget = max(0, cfg.sets.max_sets - len(profiles))
    df_sorted = df.sort_values("REVENUE_COMPANY", ascending=False).head(
        competitor_budget + len(profiles)
    )
    for key, row in df_sorted.iterrows():
        if any(p.id == str(row.get("SYNTHETIC_U")) for p, _, _ in profiles):
            continue
        profiles.append((company_profile(row, None), None, "competitor"))
        if len(profiles) >= cfg.sets.max_sets:
            break

    sets: list[RankingSet] = []
    seen: set[tuple] = set()

    for profile, watch, role in profiles:
        cands = rank_news(profile, news_pool, watch_items, cfg)
        if not cands:
            continue
        top_news = cands[: cfg.sets.max_news]
        if len(top_news) < cfg.sets.min_news:
            continue
        selected_news = top_news
        analytics_cands = rank_analytics(
            [news_by_id[c.item_id] for c in selected_news], analytics_pool, cfg
        )
        if len(analytics_cands) < cfg.sets.min_analytics:
            continue
        key = (profile.id, tuple(c.item_id for c in selected_news))
        if key in seen:
            continue
        seen.add(key)

        set_score = (
            0.6 * sum(c.score_total for c in selected_news) / len(selected_news)
            + 0.4 * analytics_cands[0].score_total
        )
        if set_score < cfg.sets.min_set_score:
            continue

        sets.append(
            RankingSet(
                set_id=str(uuid.uuid4()),
                company=_company_dict(profile, watch, role, set_score),
                news=[_news_dict(c, news_by_id[c.item_id]) for c in selected_news],
                analytics=[
                    _analytics_dict(c, analytics_by_id[c.item_id])
                    for c in analytics_cands[: cfg.sets.max_analytics]
                ],
                set_score=float(set_score),
                warnings=[],
            )
        )
        if len(sets) >= cfg.sets.max_sets:
            break

    return sets
