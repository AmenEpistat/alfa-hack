from typing import Literal

from pydantic import BaseModel, Field, field_validator


class UserResponse(BaseModel):
    id: str
    name: str
    initials: str
    role: str


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
    minutes: int
    cover: Literal["steel", "contracts", "budget"]
    sections: list[InsightSection]
    is_saved: bool = False


class Company(BaseModel):
    id: str
    name: str


class AnalysisView(BaseModel):
    company_id: str = Field(default="group")
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
    question: str = Field(min_length=1, max_length=500)
    view: AnalysisView = AnalysisView()


class AskResponse(BaseModel):
    question: str
    paragraphs: list[str]
    context: str
    references: list[str]
    suggested_view: AnalysisView | None = None


class FeedbackRequest(BaseModel):
    insight_id: str
    feedback: Literal["useful", "not-useful"]
    reason: str | None = None


class PreferenceResponse(BaseModel):
    insight_id: str
    is_saved: bool
    feedback: str | None = None
    reason: str | None = None
