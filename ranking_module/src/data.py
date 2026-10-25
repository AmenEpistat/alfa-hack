"""Input loading, validation, normalization, watchlist extraction."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger(__name__)


class DiscoveryEvidence(BaseModel):
    model_config = ConfigDict(extra="allow")
    url: str | None = None
    quote: str | None = None
    industry_match_reason: str | None = None


class WatchItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    domain: str | None = None
    specialization: str | None = None
    geography: str | None = None
    enabled: bool = True
    confirmed: bool = True
    apply_to_group: bool = False
    origin: str | None = None
    relationship: str | None = None
    industry: str | None = None
    discovery_evidence: list[DiscoveryEvidence] = Field(default_factory=list)


class EntityMatch(BaseModel):
    model_config = ConfigDict(extra="allow")
    watch_id: str | None = None
    name: str | None = None
    domain: str | None = None
    match_type: str | None = None
    relationship: str | None = None
    origin: str | None = None


class NewsItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    item_id: str
    topic: str
    document_id: str
    version_id: str | None = None
    chunk_id: str | None = None
    title: str | None = None
    text: str = ""
    source_type: str | None = None
    source_name: str | None = None
    url: str | None = None
    published_at: str | None = None
    fetched_at: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    section_title: str | None = None
    table_ids: list[str] = Field(default_factory=list)
    quality: str | None = None
    warnings: list[str] = Field(default_factory=list)
    date_in_range: bool | None = None
    duplicate_group: str | None = None
    entity_matches: list[EntityMatch] = Field(default_factory=list)


class PdfItem(NewsItem):
    pass


class CompetitorItem(NewsItem):
    pass


class Topics(BaseModel):
    model_config = ConfigDict(extra="allow")
    news: list[NewsItem] = Field(default_factory=list)
    pdf: list[PdfItem] = Field(default_factory=list)
    competitors: list[CompetitorItem] = Field(default_factory=list)


class TopicGaps(BaseModel):
    model_config = ConfigDict(extra="allow")
    news: list[str] = Field(default_factory=list)
    pdf: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)


class RankingRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    company_id: str
    topic: str | None = None
    start: str | None = None
    end: str | None = None


class Context(BaseModel):
    model_config = ConfigDict(extra="allow")
    company_industry: str | None = None
    company_region: str | None = None


class RankingInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: str = "1.0"
    run_id: str
    status: str = "partial"
    request: RankingRequest
    context: Context = Field(default_factory=Context)
    watchlist: list[WatchItem] = Field(default_factory=list)
    topics: Topics = Field(default_factory=Topics)
    topic_gaps: TopicGaps = Field(default_factory=TopicGaps)
    gaps: list[str] = Field(default_factory=list)
    errors: list[Any] = Field(default_factory=list)


def load_ranking_input(path: str | Path | dict[str, Any]) -> RankingInput:
    """Load ranking input from path or dict."""
    if isinstance(path, dict):
        return RankingInput.model_validate(path)
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return RankingInput.model_validate(raw)


def load_companies(path: str | Path | pd.DataFrame) -> pd.DataFrame:
    """Load companies dataset. Coerce column types."""
    if isinstance(path, pd.DataFrame):
        df = path.copy()
    else:
        df = pd.read_csv(path)

    if "worker_ord" in df.columns:
        df["worker_ord"] = pd.to_numeric(df["worker_ord"], errors="coerce").astype("Int8")
    if "binary_sum_products" in df.columns:
        df["binary_sum_products"] = pd.to_numeric(df["binary_sum_products"], errors="coerce").astype("Int8")
    if "GROUP_ID" in df.columns:
        df["GROUP_ID"] = df["GROUP_ID"].where(df["GROUP_ID"].notna(), None)
    for c in ("REGION", "CITY", "okved_class"):
        if c in df.columns:
            df[c] = df[c].astype("string")
    return df


def extract_watchlist(payload: RankingInput, filter_enabled: bool = True) -> list[WatchItem]:
    """Extract and normalize watchlist from ranking input payload."""
    items: list[WatchItem] = []
    for w in payload.watchlist:
        aliases = [a for a in (w.aliases or []) if a]
        domain = w.domain.lower() if w.domain else None
        items.append(
            WatchItem(
                id=w.id,
                name=w.name,
                aliases=aliases,
                domain=domain,
                specialization=w.specialization or None,
                geography=w.geography or None,
                enabled=w.enabled,
                confirmed=w.confirmed,
                apply_to_group=w.apply_to_group,
                origin=w.origin,
                relationship=w.relationship,
                industry=w.industry,
                discovery_evidence=w.discovery_evidence,
            )
        )
    if filter_enabled:
        items = [w for w in items if w.enabled]
    return items


def dedup_competitors_vs_news(topics: Topics) -> Topics:
    """Remove competitors that duplicate news items by document/version/chunk."""
    news_keys = {(n.document_id, n.version_id, n.chunk_id) for n in topics.news}
    deduped = [c for c in topics.competitors if (c.document_id, c.version_id, c.chunk_id) not in news_keys]
    return Topics(news=topics.news, pdf=topics.pdf, competitors=deduped)


def normalize_ranking_input(payload: RankingInput, drop_competitors_duplicates: bool = True) -> RankingInput:
    """Apply normalization and optional dedup of competitors vs news."""
    topics = payload.topics
    if drop_competitors_duplicates:
        topics = dedup_competitors_vs_news(topics)
    return payload.model_copy(update={"topics": topics})