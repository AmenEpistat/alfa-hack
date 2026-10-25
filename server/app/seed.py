from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Company,
    Insight,
    InsightSection,
    PurchasePlan,
    User,
)


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
                    ("Выберите компанию, период и предполагаемое изменение цены."),
                ),
                (
                    "Как получается сумма",
                    ("Стоимость закупок без фиксации умножается на изменение цены."),
                ),
                (
                    "Что обсудить с финансовой командой",
                    ("Сравните получившуюся разницу с доступным бюджетом проекта."),
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


def seed_companies(db: Session) -> None:
    companies = [
        {
            "id": "development",
            "name": "Северстрой Девелопмент",
        },
        {
            "id": "contracting",
            "name": "Северстрой Подряд",
        },
        {
            "id": "infrastructure",
            "name": "Северстрой Инфраструктура",
        },
    ]

    purchase_plan = [
        ("development", "2026-10", 350, 140, 60_000),
        ("development", "2026-11", 250, 125, 60_000),
        ("development", "2026-12", 400, 200, 60_000),
        ("contracting", "2026-10", 180, 140, 60_000),
        ("contracting", "2026-11", 220, 180, 60_000),
        ("contracting", "2026-12", 300, 200, 60_000),
        ("infrastructure", "2026-10", 120, 0, 60_000),
        ("infrastructure", "2026-11", 130, 30, 60_000),
        ("infrastructure", "2026-12", 200, 70, 60_000),
    ]

    for item in companies:
        company = db.scalar(select(Company).where(Company.id == item["id"]))

        if company is None:
            db.add(
                Company(
                    id=item["id"],
                    name=item["name"],
                )
            )

    db.flush()

    existing_plan = db.scalar(select(PurchasePlan.id).limit(1))

    if existing_plan is not None:
        return

    for company_id, month, volume, fixed_volume, price in purchase_plan:
        db.add(
            PurchasePlan(
                company_id=company_id,
                month=month,
                volume=volume,
                fixed_volume=fixed_volume,
                price=price,
            )
        )
