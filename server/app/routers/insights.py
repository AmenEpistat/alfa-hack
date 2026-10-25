from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import (
    Company,
    Insight,
    PurchasePlan,
    QuestionHistory,
    UserPreference,
)
from ..schemas import (
    AnalysisResponse,
    AnalysisTotal,
    AnalysisView,
    AskRequest,
    AskResponse,
    CompanyImpact,
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


@router.post("/analysis", response_model=AnalysisResponse)
def calculate_analysis(
    view: AnalysisView,
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    month_by_period = {
        "october": "2026-10",
        "november": "2026-11",
        "december": "2026-12",
    }

    companies = db.scalars(
        select(Company)
        .options(selectinload(Company.purchase_plan))
        .order_by(Company.name)
    ).all()

    rows: list[CompanyImpact] = []

    for company in companies:
        if view.company_id != "group" and view.company_id != company.id:
            continue

        records = [
            row
            for row in company.purchase_plan
            if (view.period == "quarter" or row.month == month_by_period[view.period])
        ]

        volume = sum(row.volume for row in records)
        fixed_volume = sum(row.fixed_volume for row in records)
        open_volume = volume - fixed_volume
        budget = sum(row.volume * row.price for row in records)
        exposed_budget = sum(
            (row.volume - row.fixed_volume) * row.price for row in records
        )
        delta = round(exposed_budget * view.price_change_pct / 100)

        rows.append(
            CompanyImpact(
                id=company.id,
                name=company.name,
                volume=volume,
                fixed_volume=fixed_volume,
                open_volume=open_volume,
                budget=budget,
                exposed_budget=exposed_budget,
                delta=delta,
            )
        )

    total = AnalysisTotal(
        volume=sum(row.volume for row in rows),
        fixed_volume=sum(row.fixed_volume for row in rows),
        open_volume=sum(row.open_volume for row in rows),
        budget=sum(row.budget for row in rows),
        exposed_budget=sum(row.exposed_budget for row in rows),
        delta=sum(row.delta for row in rows),
    )

    return AnalysisResponse(
        view=view,
        rows=rows,
        total=total,
    )


@router.post("/ask", response_model=AskResponse)
def ask_question(
    payload: AskRequest,
    user_id: str = Query(default="anna"),
    db: Session = Depends(get_db),
) -> AskResponse:
    insight = db.scalar(select(Insight).where(Insight.id == payload.insight_id))

    if insight is None:
        raise HTTPException(
            status_code=404,
            detail="Инсайт не найден.",
        )

    question = payload.question.lower()
    suggested_view = None
    references = ["plan"]

    paragraphs = [
        "Начните с проверки открытого объёма закупок и условий фиксации цены.",
        (
            "Сценарий показывает потенциальную разницу бюджета, "
            "но не является прогнозом фактической цены поставщика."
        ),
    ]

    if "рын" in question or "worldsteel" in question:
        paragraphs = [
            (
                "Обзор рынка можно использовать как повод проверить "
                "договоры и ближайшие закупки."
            ),
            (
                "Публичные данные о спросе на сталь не подтверждают "
                "изменение цены именно в вашей компании."
            ),
        ]
        references = ["market", "plan"]

    if "бюдж" in question or "сумм" in question:
        paragraphs = [
            (
                "Для оценки бюджетного риска умножьте стоимость "
                "открытого объёма на предполагаемое изменение цены."
            ),
            (
                f"В текущем сценарии изменение цены составляет "
                f"{payload.view.price_change_pct:g}%."
            ),
        ]

    if "ноябр" in question:
        suggested_view = payload.view.model_copy(update={"period": "november"})

    if "декабр" in question:
        suggested_view = payload.view.model_copy(update={"period": "december"})

    if "девелоп" in question:
        suggested_view = payload.view.model_copy(update={"company_id": "development"})

    response = AskResponse(
        question=payload.question,
        paragraphs=paragraphs,
        context=(
            "Ответ сформирован на основе данных из базы и демонстрационного инсайта."
        ),
        references=references,
        suggested_view=suggested_view,
    )

    db.add(
        QuestionHistory(
            user_id=user_id,
            insight_id=payload.insight_id,
            question=payload.question,
            answer="\n\n".join(paragraphs),
        )
    )
    db.commit()

    return response


@router.get("/export/purchase-plan.csv")
def export_purchase_plan_csv(
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(PurchasePlan)
        .options(selectinload(PurchasePlan.company))
        .order_by(
            PurchasePlan.company_id,
            PurchasePlan.month,
        )
    ).all()

    lines = [
        "УЧЕБНЫЕ ДАННЫЕ;Не являются данными клиента или банка",
        ("Компания;Месяц;План закупок, т;Зафиксированная цена, т;Плановая цена, руб/т"),
    ]

    for row in rows:
        lines.append(
            ";".join(
                [
                    row.company.name,
                    row.month,
                    str(row.volume),
                    str(row.fixed_volume),
                    str(row.price),
                ]
            )
        )

    return Response(
        content="\ufeff" + "\r\n".join(lines),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": ('attachment; filename="purchase-plan.csv"'),
        },
    )
