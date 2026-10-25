from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from alfa_insights.api import (
    health as ranking_health,
)
from alfa_insights.api import (
    run_ranking,
    validate_payload,
)
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Company, RankingItem, RankingRun, RankingSetRecord

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

router = APIRouter(
    prefix="/api/ranking",
    tags=["ranking"],
)


def _ranking_config_path() -> Path:
    return REPOSITORY_ROOT / "ranking_module" / "config.yaml"


def _ranking_overrides(
    overrides: dict[str, Any] | None,
) -> dict[str, Any]:
    result = dict(overrides or {})

    paths = dict(result.get("paths") or {})
    paths.setdefault("root", str(REPOSITORY_ROOT))
    paths.setdefault(
        "companies",
        str(REPOSITORY_ROOT / "ranking_module" / "data" / "companies.csv"),
    )
    result["paths"] = paths

    return result


def _companies_dataframe(
    db: Session,
) -> pd.DataFrame:
    companies = db.scalars(select(Company).order_by(Company.name)).all()

    if not companies:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []

    for company in companies:
        row = dict(company.data or {})

        row.setdefault("SYNTHETIC_U", company.id)
        row.setdefault("name", company.name)
        row.setdefault("REVENUE_COMPANY", 0)

        rows.append(row)

    dataframe = pd.DataFrame(rows)

    required_columns: dict[str, Any] = {
        "SYNTHETIC_U": None,
        "REVENUE_COMPANY": 0,
        "MAINOKVED_CODE": None,
        "MAINOKVED_NAME": None,
        "REGION": None,
        "CITY": None,
        "GROUP_ID": None,
        "CL_TYPE": None,
        "worker_ord": None,
        "binary_sum_products": None,
        "worker_mid_approx": None,
        "age_mid": None,
        "okved_class": None,
    }

    for column, default_value in required_columns.items():
        if column not in dataframe.columns:
            dataframe[column] = default_value

    return dataframe


def _iter_input_items(payload: dict[str, Any]):
    topics = payload.get("topics") or {}

    for item in topics.get("news") or []:
        yield "news", item

    for item in topics.get("pdf") or []:
        yield "pdf", item

    for item in topics.get("competitors") or []:
        yield "competitor", item


def _persist_result(
    db: Session,
    payload: dict[str, Any],
    result: dict[str, Any],
) -> RankingRun:
    existing = db.scalar(
        select(RankingRun).where(
            RankingRun.run_id == result["run_id"],
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Результат с run_id={result['run_id']} уже существует.",
        )

    request = payload.get("request") or {}

    run = RankingRun(
        run_id=result["run_id"],
        company_id=request.get("company_id"),
        topic=request.get("topic"),
        status=result.get("status", "partial"),
        schema_version=result.get("schema_version"),
        request_payload=payload,
        result_payload=result,
        diagnostics=result.get("diagnostics") or {},
    )

    db.add(run)
    db.flush()

    for kind, item in _iter_input_items(payload):
        if not isinstance(item, dict):
            continue

        item_id = item.get("item_id")
        if not item_id:
            continue

        db.add(
            RankingItem(
                run_id=run.id,
                item_id=str(item_id),
                document_id=item.get("document_id"),
                kind=kind,
                title=item.get("title"),
                payload=item,
            )
        )

    for ranking_set in result.get("sets") or []:
        company = ranking_set.get("company") or {}

        db.add(
            RankingSetRecord(
                run_id=run.id,
                set_id=str(ranking_set.get("set_id")),
                company_id=company.get("id"),
                set_score=float(ranking_set.get("set_score") or 0),
                payload=ranking_set,
            )
        )

    db.commit()
    db.refresh(run)

    return run


@router.get("/health")
def health() -> dict[str, Any]:
    """
    Проверка доступности ranking_module и его кешей.
    """
    try:
        return ranking_health(
            config=_ranking_config_path(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Ranking module недоступен: {exc}",
        ) from exc


@router.post("/validate")
def validate(
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """
    Валидация тела для ранжирования без загрузки моделей.
    """
    warnings = validate_payload(payload)

    return {
        "valid": not any(
            warning.startswith("payload validation failed") for warning in warnings
        ),
        "warnings": warnings,
    }


def _parse_overrides(
    overrides: str | None,
) -> dict[str, Any] | None:
    if not overrides:
        return None

    try:
        value = json.loads(overrides)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail="Параметр overrides должен быть JSON-объектом.",
        ) from exc

    if not isinstance(value, dict):
        raise HTTPException(
            status_code=422,
            detail="Параметр overrides должен быть JSON-объектом.",
        )

    return value


@router.post("/run")
def run(
    payload: dict[str, Any] = Body(...),
    overrides: str | None = Query(default=None),
    persist: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Запуск ранжинрования.
    """
    companies = _companies_dataframe(db)

    if companies.empty:
        raise HTTPException(
            status_code=422,
            detail=("В базе отсутствуют компании для ранжирования. "),
        )

    try:
        result = run_ranking(
            payload=payload,
            companies=companies,
            config=_ranking_config_path(),
            overrides=_ranking_overrides(
                _parse_overrides(overrides),
            ),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка выполнения пайплайна ранжирования: {exc}",
        ) from exc

    if persist:
        _persist_result(
            db=db,
            payload=payload,
            result=result,
        )

    return result


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    run_record = db.scalar(
        select(RankingRun).where(
            RankingRun.run_id == run_id,
        )
    )

    if run_record is None:
        raise HTTPException(
            status_code=404,
            detail="Запуск ранжирования не найден.",
        )

    return run_record.result_payload
