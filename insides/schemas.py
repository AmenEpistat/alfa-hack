"""Strict inference contract for multi-source insights and source references."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .categories import get_category
from .audiences import AudienceType, get_audience


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRef(StrictModel):
    evidence_id: str = Field(min_length=1)
    quote: str = Field(min_length=8, max_length=600)


class Claim(StrictModel):
    text: str = Field(min_length=8, max_length=1400)
    basis: Literal["source_fact", "bank_position", "model_inference", "assumption"]
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=5)
    company_fields: list[str] = Field(default_factory=list, max_length=12)


class Event(StrictModel):
    summary: Claim
    key_facts: list[Claim] = Field(min_length=1, max_length=4)
    participants: list[Claim] = Field(min_length=1, max_length=3)
    timing: Claim | None
    causes: list[Claim] = Field(max_length=3)
    assumptions: list[Claim] = Field(max_length=3)
    missing_information: list[str] = Field(max_length=10)


class Consequence(StrictModel):
    kind: Literal["risk", "opportunity", "uncertain"]
    claim: Claim
    conditions: list[str] = Field(min_length=1, max_length=5)
    horizon: str | None


class Action(StrictModel):
    kind: Literal["analysis_question", "scenario", "action"]
    action: str = Field(min_length=8, max_length=900)
    rationale: Claim
    checks: list[str] = Field(min_length=1, max_length=5)


class BankAssessment(StrictModel):
    status: Literal["documented_context", "insufficient_evidence"]
    bank_statements: list[Claim] = Field(max_length=3)
    model_interpretation: Claim | None
    limitations: list[str] = Field(min_length=1, max_length=10)


class SourceSummary(StrictModel):
    document_id: str = Field(min_length=1)
    summary: Claim


CategoryId = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


class InsightCategory(StrictModel):
    id: CategoryId
    slug: str
    name: str
    description: str
    image_key: str
    image_description: str


class TargetAudience(StrictModel):
    type: AudienceType
    name: str
    priorities: list[str]
    action_scope: str
    search_focus: str


class ProductDetails(StrictModel):
    product_id: str
    name: str
    url: str
    description: str
    applicability: str


class ProductRecommendationDraft(StrictModel):
    product_id: str = Field(min_length=1)
    problem: Claim
    capability_quote: str = Field(min_length=8, max_length=600)
    mechanism: str = Field(min_length=15, max_length=700)
    application: str = Field(min_length=15, max_length=500)
    conditions: list[str] = Field(min_length=1, max_length=4)

    @field_validator("capability_quote", "mechanism", "application")
    @classmethod
    def nonblank_product_text(cls, value):
        if not value.strip():
            raise ValueError("Product recommendation text must not be blank")
        return value


class ProductRecommendation(ProductRecommendationDraft):
    product: ProductDetails

    @model_validator(mode="after")
    def matching_product_identity(self):
        if self.product_id != self.product.product_id:
            raise ValueError("Product metadata must match product_id")
        return self


class InsightDraft(StrictModel):
    audience_type: AudienceType
    audience_rationale: str = Field(min_length=15, max_length=600)
    product_recommendations: list[ProductRecommendationDraft] = Field(min_length=0, max_length=3)

    category_id: CategoryId = Field(description="Exactly one dominant business category, integer 1-10.")

    @field_validator("category_id", mode="before")
    @classmethod
    def category_is_one_integer(cls, value):
        get_category(value)
        return value

    title: str = Field(min_length=8, max_length=240)
    lead: Claim | None = Field(default=None, description="Brief insight takeaway in 1-2 grounded sentences.")
    source_summaries: list[SourceSummary] = Field(default_factory=list, description="1-2 supported sentences about each used document.")
    primary_document_id: str
    what_happened: Event
    why_important_for_company: list[Claim] = Field(min_length=1, max_length=3)
    possible_consequences: list[Consequence] = Field(min_length=1, max_length=3)
    relevant_actions: list[Action] = Field(min_length=1, max_length=3)
    bank_assessment: BankAssessment


class SynthesisInsightDraft(InsightDraft):
    source_document_ids: list[str] = Field(min_length=2, max_length=5)
    events: list[Claim] = Field(min_length=2, max_length=5)
    synthesis: Claim


class Foundation(StrictModel):
    documents: list[dict]
    company_features: list[dict]
    claim_links: list[dict]


class InsightResult(InsightDraft):
    category: InsightCategory
    target_audience: TargetAudience
    product_recommendations: list[ProductRecommendation] = Field(min_length=0, max_length=3)
    insight_id: str
    generation_order: int
    primary_topic: Literal["news", "pdf", "competitors"]
    input_document_rank: int | None
    source_document_ids: list[str] = Field(default_factory=list)
    events: list[Claim] = Field(default_factory=list)
    synthesis: Claim | None = None
    synthesis_group_id: str | None = None
    topics: list[str] = Field(default_factory=list)
    foundation: Foundation
    evidence_status: Literal["requires_review", "traceable"]
    warnings: list[str]
    validation: dict
    markdown: str = Field(default="", description="Standalone AI-labelled article with a brief lead and its own documentary sources.")
    sources_markdown: str = Field(default="", description="Separate annotated list of the same sources with matching S labels.")

    @model_validator(mode="after")
    def category_metadata_matches_catalog(self):
        if self.target_audience.model_dump() != get_audience(self.audience_type):
            raise ValueError("Target audience metadata must match audience_type")
        if self.category.model_dump() != get_category(self.category_id):
            raise ValueError("Category metadata must match the canonical category_id")
        return self


class GenerationResult(StrictModel):
    schema_version: Literal["1.0"]
    run_id: str
    input_run_id: str | None
    input_canonical_sha256: str
    input_file_sha256: str | None = None
    generated_at: str
    status: Literal["running", "completed", "partial", "failed"]
    company_input: dict
    target_audience: TargetAudience
    product_catalog: dict
    self_check: dict = Field(default_factory=dict)
    input_status: str | None
    input_already_ranked: Literal[True]
    generation_policy: dict
    insights: list[InsightResult]
    errors: list[dict]
    input_warnings: list[str]
    limitations: list[str]
    usage: dict
    recovery: dict | None = None
    markdown: str = Field(default="", description="Reserved for loading previous outputs; use insights[i].markdown for articles.")

    @model_validator(mode="after")
    def personalization_and_catalog_consistent(self):
        catalog = {p["product_id"]: p for p in self.product_catalog.get("products", [])}
        for insight in self.insights:
            if insight.target_audience != self.target_audience:
                raise ValueError("Insight and result target audience must match")
            for recommendation in insight.product_recommendations:
                if recommendation.product.model_dump() != catalog.get(recommendation.product_id):
                    raise ValueError("Product metadata must match the generation catalog snapshot")
        return self
