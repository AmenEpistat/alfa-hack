from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Company,
    Insight,
    InsightSection,
    PurchasePlan,
    User,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMPANIES_PATH = REPOSITORY_ROOT / "ranking_module" / "data" / "companies.csv"


def seed_database(db: Session) -> None:
    seed_users(db)
    seed_insights(db)
    seed_companies(db)

    db.commit()


def seed_users(db: Session) -> None:
    users = [
        User(
            id="anna",
            name="Анна Смирнова",
            initials="АС",
            role="Финансовый директор",
            email="anna@example.com",
        ),
        User(
            id="ilya",
            name="Илья Воронов",
            initials="ИВ",
            role="Казначей",
            email="ilya@example.com",
        ),
    ]

    for user in users:
        exists = db.scalar(select(User).where(User.id == user.id))

        if exists is None:
            db.add(user)


def seed_insights(db: Session) -> None:
    insights = [
        {
            "id": "steel-cost",
            "topic": "Рынок",
            "title": "Проверьте цены в договорах на сталь",
            "summary": (
                "Уточните стоимость ближайших заказов. Если поставщик "
                "может изменить цену, дополнительные расходы лягут "
                "на бюджет проекта."
            ),
            "minutes": 3,
            "cover": "steel",
            "sections": [
                (
                    "Начните с ближайшего заказа",
                    (
                        "Найдите договоры, в которых поставщик ещё может "
                        "изменить цену. Зафиксируйте дату, объём и условия "
                        "пересмотра."
                    ),
                ),
                (
                    "Обзор рынка — повод проверить, а не покупать",
                    (
                        "Публичный обзор worldsteel описывает мировой спрос "
                        "на сталь, но не заменяет проверку конкретных "
                        "договоров."
                    ),
                ),
                (
                    "Что это значит для вашей группы",
                    (
                        "Сначала проверьте открытый объём закупок и сроки "
                        "фиксации цены в каждой компании группы."
                    ),
                ),
            ],
        },
        {
            "id": "price-fixation",
            "topic": "Закупки",
            "title": "Какие закупки зависят от цены поставщика",
            "summary": (
                "Отделите заказы с подтверждённой стоимостью от тех, "
                "для которых цену ещё могут пересмотреть."
            ),
            "minutes": 4,
            "cover": "contracts",
            "sections": [
                (
                    "Разделите план на две части",
                    (
                        "Отдельно посчитайте объём с зафиксированной ценой "
                        "и объём, который остаётся открытым."
                    ),
                ),
                (
                    "Проверьте срок фиксации",
                    (
                        "Для каждого заказа сверяйте подтверждённую цену, "
                        "объём и период действия условий поставщика."
                    ),
                ),
                (
                    "С чего начать разговор с поставщиком",
                    (
                        "Уточните стоимость ближайшего заказа и дату "
                        "окончания периода фиксации."
                    ),
                ),
            ],
        },
        {
            "id": "purchase-budget",
            "topic": "Финансы",
            "title": "Как проверить запас бюджета на материалы",
            "summary": (
                "Один сценарий изменения цены поможет увидеть, какую "
                "сумму стоит обсудить с финансовой командой."
            ),
            "minutes": 3,
            "cover": "budget",
            "sections": [
                (
                    "Проверьте одно допущение",
                    "Выберите компанию, период и предполагаемое изменение цены.",
                ),
                (
                    "Как получается сумма",
                    "Стоимость закупок без фиксации умножается на изменение цены.",
                ),
                (
                    "Что обсудить с финансовой командой",
                    "Сравните получившуюся разницу с доступным бюджетом проекта.",
                ),
            ],
        },
    ]

    for item in insights:
        insight = db.scalar(select(Insight).where(Insight.id == item["id"]))

        if insight is not None:
            continue

        insight = Insight(
            id=item["id"],
            topic=item["topic"],
            title=item["title"],
            summary=item["summary"],
            minutes=item["minutes"],
            cover=item["cover"],
        )

        db.add(insight)
        db.flush()

        for position, section in enumerate(item["sections"]):
            db.add(
                InsightSection(
                    insight_id=insight.id,
                    title=section[0],
                    text=section[1],
                    position=position,
                )
            )


def _parse_csv_value(value: str | None) -> Any:
    """
    Преобразовать значения из CSV в типы, совместимые с JSON.
    """
    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    lowered = value.lower()

    if lowered in {"true", "да", "yes"}:
        return True

    if lowered in {"false", "нет", "no"}:
        return False

    try:
        if "." in value:
            return float(value)

        return int(value)
    except ValueError:
        return value


def _company_id(row: dict[str, str | None]) -> str | None:
    for field in (
        "SYNTHETIC_U",
        "id",
        "ID",
        "company_id",
        "COMPANY_ID",
    ):
        value = row.get(field)

        if value:
            return str(value).strip()

    return None


def _company_name(
    row: dict[str, str | None],
    fallback_id: str,
) -> str:
    for field in (
        "name",
        "NAME",
        "company_name",
        "COMPANY_NAME",
        "short_name",
        "SHORT_NAME",
    ):
        value = row.get(field)

        if value:
            return str(value).strip()

    return fallback_id


def seed_companies(db: Session) -> None:
    """
    Загружает датасет ranking_module/data/companies.csv в БД.
    """
    if not COMPANIES_PATH.exists():
        return

    # Bulk upserts preserve existing company IDs and avoid one SELECT per CSV row.
    batch = []
    def save_batch(values):
        if db.bind.dialect.name == 'sqlite':
            from sqlalchemy.dialects.sqlite import insert
            statement = insert(Company).values(values)
            db.execute(statement.on_conflict_do_update(index_elements=['id'], set_={
                'name': statement.excluded.name, 'data': statement.excluded.data,
            }))
        else:
            for value in values:
                db.merge(Company(**value))

    with COMPANIES_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        for raw_row in reader:
            row = {key: value for key, value in raw_row.items() if key is not None}

            company_id = _company_id(row)

            if not company_id:
                continue

            company_name = _company_name(row, company_id)

            data = {key: _parse_csv_value(value) for key, value in row.items() if key}

            data.setdefault("SYNTHETIC_U", company_id)
            data.setdefault("name", company_name)

            batch.append({"id": company_id, "name": company_name, "data": data})
            if len(batch) >= 500:
                save_batch(batch)
                batch.clear()
        if batch:
            save_batch(batch)
    db.flush()
