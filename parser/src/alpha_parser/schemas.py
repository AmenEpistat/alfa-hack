from datetime import date, datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Chunk(StrictModel):
    chunk_id: str = ""
    document_id: str = ""
    version_id: str = ""
    section_title: str | None = None
    text: str
    page_start: int | None = None
    page_end: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    table_ids: list[str] = Field(default_factory=list)


class Document(StrictModel):
    document_id: str = ""
    version_id: str = ""
    previous_version_id: str | None = None
    source_type: Literal["alpha_pdf", "external"]
    source_name: str
    original_filename: str | None = None
    url: str | None = None
    original_url: str | None = None
    title: str
    author: str | None = None
    published_at: str | None = None
    publication_date_evidence: dict | None = None
    updated_at: str | None = None
    event_at: str | None = None
    fetched_at: str = Field(default_factory=utcnow)
    language: str | None = None
    content_hash: str
    extractor_version: str
    config_hash: str
    quality: Literal["extracted", "requires_review", "failed"]
    warnings: list[str] = Field(default_factory=list)
    original_path: str
    duplicate_group: str | None = None
    tables: list[dict] = Field(default_factory=list)
    pages: list[dict] = Field(default_factory=list)


class WatchCompany(StrictModel):
    name: str = Field(min_length=2, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    domain: str = Field(min_length=3, max_length=253, pattern=r"^[a-zA-Z0-9.-]+$")
    specialization: str | None = None
    geography: str | None = None
    enabled: bool = True
    confirmed: bool = False
    apply_to_group: bool = False
    origin: Literal["manual", "industry_agent"] = "manual"
    relationship: Literal["competitor", "industry_peer"] = "competitor"
    industry: str | None = None
    discovery_evidence: list[dict] = Field(default_factory=list)


class ResearchInput(StrictModel):
    """Public request: the platform resolves the history window internally."""
    company_id: str
    group_id: str | None = None
    role: str | None = None
    topic: str = Field(min_length=2, max_length=500)
    external: bool = True
    max_steps: int | None = Field(None, ge=1, le=30)


class ResearchRequest(ResearchInput):
    """Internal resolved request; also used to reproduce saved runs."""
    start: date
    end: date

    @model_validator(mode="after")
    def interval(self):
        if self.start > self.end:
            raise ValueError("start must be <= end")
        return self


def resolve_research_input(value):
    from .periods import history_window
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    spec = ResearchInput.model_validate(payload)
    window = history_window()
    return ResearchRequest(**spec.model_dump(), start=window.start, end=window.end)


class Action(StrictModel):
    tool: Literal["get_context", "search_alpha", "search_local", "read_rss", "search_web", "fetch_article", "parse_pdf", "search_competitor_news", "record_peer", "record_peers", "finish"]
    arguments: dict = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=1000)


class CompetitorMatch(StrictModel):
    watch_id: str
    name: str
    domain: str
    match_type: Literal["official_domain_and_name", "name_mention", "official_domain"]
    relationship: Literal["competitor", "industry_peer"] = "competitor"
    origin: Literal["manual", "industry_agent"] = "manual"


class PeerDiscoveryRequest(StrictModel):
    industry: str = Field(min_length=2, max_length=500)
    region: str | None = Field(None, max_length=250)
    limit: int = Field(3, ge=1, le=10)
    exclude_domains: list[str] = Field(default_factory=list, max_length=20)


class PeerCandidate(StrictModel):
    name: str = Field(min_length=2, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    domain: str = Field(min_length=3, max_length=253, pattern=r"^[a-zA-Z0-9.-]+$")
    evidence_url: str
    industry_evidence: str = Field(min_length=15, max_length=600)
    industry_match_reason: str = Field(min_length=5, max_length=600)


class PeerCandidates(StrictModel):
    companies: list[PeerCandidate] = Field(min_length=1, max_length=10)


class CollectionLimits(StrictModel):
    min_sources_per_topic: int = Field(5, ge=5, le=100)
    min_sources: int = Field(10, ge=10, le=100)
    news_limit: int = Field(5, ge=0, le=20)
    competitor_limit: int = Field(5, ge=0, le=10)
    pdf_limit: int = Field(15, ge=0, le=100)


class RankingItem(StrictModel):
    item_id: str
    topic: Literal["news", "pdf", "competitors"]
    document_id: str
    version_id: str
    chunk_id: str
    title: str
    text: str = Field(min_length=1)
    source_type: Literal["alpha_pdf", "external"]
    source_name: str
    original_filename: str | None = None
    url: str | None = None
    published_at: str | None = None
    publication_date_evidence: dict | None = None
    fetched_at: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    section_title: str | None = None
    table_ids: list[str] = Field(default_factory=list)
    quality: Literal["extracted", "requires_review"]
    warnings: list[str] = Field(default_factory=list)
    date_in_range: bool | None = None
    duplicate_group: str | None = None
    entity_matches: list[CompetitorMatch] = Field(default_factory=list)


class RankingTopics(StrictModel):
    news: list[RankingItem] = Field(default_factory=list)
    pdf: list[RankingItem] = Field(default_factory=list)
    competitors: list[RankingItem] = Field(default_factory=list)


class SourceCoverage(StrictModel):
    min_sources_per_topic: int = Field(0, ge=0, le=100)
    topic_minimums_met: bool = False
    topic_shortfalls: dict[str, int] = Field(default_factory=dict)
    min_sources: int = Field(10, ge=10, le=100)
    total_sources: int = Field(0, ge=0)
    by_topic: dict[str, int] = Field(default_factory=dict)
    missing_topics: list[str] = Field(default_factory=list)
    minimum_met: bool = False
    all_topics_present: bool = False
    requirements_met: bool = False
    counting_unit: str


class RankingInput(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    status: str
    request: dict
    context: dict | None = None
    company_input: dict | None = None
    target_audience: dict | None = None
    preprocessing_input: dict | None = None
    company_analysis_context: dict | None = None
    watchlist: list[dict] = Field(default_factory=list)
    topics: RankingTopics = Field(default_factory=RankingTopics)
    competitor_events: list[dict] = Field(default_factory=list)
    competitor_brief: dict | None = None
    competitor_news_policy: dict | None = None
    competitor_diversity: dict | None = None
    coverage: SourceCoverage | None = None
    search_window: dict | None = None
    topic_gaps: dict[str, list[str]] = Field(default_factory=dict)
    gaps: list[str] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)


class CompanyInput(BaseModel):
    """Preprocessed company profile retained locally; only a whitelist is used for public search."""
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True, allow_inf_nan=False)
    company_id: str = Field(min_length=1, max_length=100)
    industry: str = Field(min_length=2, max_length=500)
    okved_code: str | None = None
    region: str | None = Field(None, max_length=250)
    city: str | None = Field(None, max_length=250)
    group_id: str | None = Field(None, max_length=100)
    client_type: Literal["CLIENT"]
    group_context: dict[str, list[str]] = Field(default_factory=dict)
    identity_ambiguous: bool = False
    source_company_id: str | None = None
    source_row: int | None = Field(None, ge=2)
    attributes: dict = Field(default_factory=dict)
    features: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    def public_context(self):
        return {
            "company_industry": self.industry, "company_region": self.region,
            "company_city": self.city, "company_okved_code": self.okved_code,
            "industries": list(dict.fromkeys([self.industry, *self.group_context.get("industries", [])]))[:12],
            "regions": list(dict.fromkeys([r for r in [self.region, *self.group_context.get("regions", [])] if r]))[:12],
        }

