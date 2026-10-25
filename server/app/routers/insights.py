from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import (
    Company,
    Insight,
    UserPreference,
)
from ..schemas import (
    InsightResponse,
    InsightSection,
)

router = APIRouter(prefix="/api/insights", tags=["insights"])


def get_preference(
    db: Session,
    user_id: str,
    insight_id: str,
) -> UserPreference | None:
    return db.scalar(
        select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.insight_id == insight_id,
        )
    )


def serialize_insight(
    insight: Insight,
    saved: bool = False,
) -> InsightResponse:
    assert insight.cover in ("steel", "contracts", "budget")
    return InsightResponse(
        id=insight.id,
        topic=insight.topic,
        title=insight.title,
        summary=insight.summary,
        minutes=insight.minutes,
        cover=insight.cover,
        sections=[
            InsightSection(title=section.title, text=section.text)
            for section in insight.sections
        ],
        is_saved=saved,
    )


def load_insights(db: Session) -> list[Insight]:
    return list(
        db.scalars(
            select(Insight)
            .options(selectinload(Insight.sections))
            .order_by(Insight.created_at)
        ).all()
    )


@router.get("", response_model=list[InsightResponse])
def list_insights(
    user_id: str = Query(default="anna"),
    db: Session = Depends(get_db),
) -> list[InsightResponse]:
    result = []

    for insight in load_insights(db):
        preference = get_preference(
            db,
            user_id,
            insight.id,
        )

        result.append(
            serialize_insight(
                insight,
                saved=bool(preference and preference.is_saved),
            )
        )

    return result


@router.get("/{insight_id}", response_model=InsightResponse)
def get_insight(
    insight_id: str,
    user_id: str = Query(default="anna"),
    db: Session = Depends(get_db),
) -> InsightResponse:
    insight = db.scalar(
        select(Insight)
        .options(selectinload(Insight.sections))
        .where(Insight.id == insight_id)
    )

    if insight is None:
        raise HTTPException(
            status_code=404,
            detail="Инсайт не найден.",
        )

    preference = get_preference(
        db,
        user_id,
        insight_id,
    )

    return serialize_insight(
        insight,
        saved=bool(preference and preference.is_saved),
    )


@router.get("/meta/companies")
def get_companies(
    db: Session = Depends(get_db),
) -> list[dict[str, str]]:
    companies = db.scalars(select(Company).order_by(Company.name)).all()

    return [
        {
            "id": company.id,
            "name": company.name,
        }
        for company in companies
    ]
