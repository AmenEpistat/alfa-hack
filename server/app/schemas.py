from typing import Literal

from pydantic import BaseModel, Field, field_validator


class UserResponse(BaseModel):
    id: str
    name: str
    initials: str
    role: str
    audience_type: str


class LoginRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=50)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class InsightSection(BaseModel):
    title: str
    text: str


class InsightResponse(BaseModel):
    id: str
    topic: str
    title: str
    summary: str
    minutes: int | None = None
    cover: str
    category_id: int | str | None = None
    category_name: str | None = None
    cover_url: str | None = None
    cover_background: str | None = None
    sections: list[InsightSection]
    content: str
    source_ids: list[str] = Field(default_factory=list)
    prepared_at: str | None = None
    expires_at: str | None = None
    generation_method: Literal["ai", "ai_assisted", "editorial", "rules"] = "editorial"
    audience_type: str | None = None
    product_recommendations: list[dict] = Field(default_factory=list)
    is_saved: bool = False


class Company(BaseModel):
    id: str
    name: str


class AnalysisView(BaseModel):
    company_id: Literal["group", "development", "contracting", "infrastructure"] = "group"
    period: Literal["october", "november", "december", "quarter"] = "quarter"
    price_change_pct: float = Field(default=10)

    @field_validator("price_change_pct")
    @classmethod
    def validate_price_change(cls, value: float) -> float:
        if not -30 <= value <= 30:
            raise ValueError("Сценарное изменение цены должно быть от -30 до +30%.")

        return value


class CompanyImpact(BaseModel):
    id: str
    name: str
    volume: float
    fixed_volume: float
    open_volume: float
    budget: float
    exposed_budget: float
    delta: float


class AnalysisTotal(BaseModel):
    volume: float
    fixed_volume: float
    open_volume: float
    budget: float
    exposed_budget: float
    delta: float


class AnalysisResponse(BaseModel):
    view: AnalysisView
    rows: list[CompanyImpact]
    total: AnalysisTotal


class AskRequest(BaseModel):
    insight_id: str
    question: str = Field(min_length=1, max_length=500, pattern=r"\S")
    view: AnalysisView = Field(default_factory=AnalysisView)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=20)


class AskResponse(BaseModel):
    kind: str = "unsupported"
    question: str
    paragraphs: list[str]
    context: str
    references: list[str]
    suggested_view: AnalysisView | None = None
    content: str
    citations: dict[int, list[str]] = Field(default_factory=dict)
    generation_method: Literal["ai", "ai_assisted", "editorial", "rules"] = "rules"


class FeedbackRequest(BaseModel):
    insight_id: str
    feedback: Literal["useful", "not-useful"] | None
    reason: str | None = Field(default=None, max_length=100)


class PreferenceResponse(BaseModel):
    insight_id: str
    is_saved: bool
    feedback: str | None = None
    reason: str | None = None
