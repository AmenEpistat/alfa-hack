from dataclasses import dataclass


@dataclass(frozen=True)
class DemoUser:
    id: str
    name: str
    initials: str
    role: str


DEMO_USERS = [
    DemoUser(
        id="anna",
        name="Анна Смирнова",
        initials="АС",
        role="Финансовый директор",
    ),
    DemoUser(
        id="ilya",
        name="Илья Воронов",
        initials="ИВ",
        role="Казначей",
    ),
]


COMPANIES = [
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


PURCHASE_PLAN = [
    {
        "company_id": "development",
        "month": "2026-10",
        "volume": 350,
        "fixed_volume": 140,
        "price": 60_000,
    },
    {
        "company_id": "development",
        "month": "2026-11",
        "volume": 250,
        "fixed_volume": 125,
        "price": 60_000,
    },
    {
        "company_id": "development",
        "month": "2026-12",
        "volume": 400,
        "fixed_volume": 200,
        "price": 60_000,
    },
    {
        "company_id": "contracting",
        "month": "2026-10",
        "volume": 180,
        "fixed_volume": 140,
        "price": 60_000,
    },
    {
        "company_id": "contracting",
        "month": "2026-11",
        "volume": 220,
        "fixed_volume": 180,
        "price": 60_000,
    },
    {
        "company_id": "contracting",
        "month": "2026-12",
        "volume": 300,
        "fixed_volume": 200,
        "price": 60_000,
    },
    {
        "company_id": "infrastructure",
        "month": "2026-10",
        "volume": 120,
        "fixed_volume": 0,
        "price": 60_000,
    },
    {
        "company_id": "infrastructure",
        "month": "2026-11",
        "volume": 130,
        "fixed_volume": 30,
        "price": 60_000,
    },
    {
        "company_id": "infrastructure",
        "month": "2026-12",
        "volume": 200,
        "fixed_volume": 70,
        "price": 60_000,
    },
]


INSIGHTS = [
    {
        "id": "steel-cost",
        "topic": "Рынок",
        "title": "Проверьте цены в договорах на сталь",
        "summary": (
            "Уточните стоимость ближайших заказов. Если поставщик может "
            "изменить цену, дополнительные расходы лягут на бюджет проекта."
        ),
        "minutes": 3,
        "cover": "steel",
        "sections": [
            {
                "title": "Начните с ближайшего заказа",
                "text": (
                    "Найдите договоры, в которых поставщик ещё может изменить "
                    "цену. Зафиксируйте дату, объём и условия пересмотра."
                ),
            },
            {
                "title": "Обзор рынка — повод проверить, а не покупать",
                "text": (
                    "Публичный обзор worldsteel описывает мировой спрос на "
                    "сталь, но не заменяет проверку конкретных договоров."
                ),
            },
            {
                "title": "Что это значит для вашей группы",
                "text": (
                    "Сначала проверьте открытый объём закупок и сроки фиксации "
                    "цены в каждой компании группы."
                ),
            },
        ],
    },
    {
        "id": "price-fixation",
        "topic": "Закупки",
        "title": "Какие закупки зависят от цены поставщика",
        "summary": (
            "Отделите заказы с подтверждённой стоимостью от тех, для которых "
            "цену ещё могут пересмотреть."
        ),
        "minutes": 4,
        "cover": "contracts",
        "sections": [
            {
                "title": "Разделите план на две части",
                "text": (
                    "Отдельно посчитайте объём с зафиксированной ценой и объём, "
                    "который остаётся открытым."
                ),
            },
            {
                "title": "Проверьте срок фиксации",
                "text": (
                    "Для каждого заказа сверяйте подтверждённую цену, объём и "
                    "период действия условий поставщика."
                ),
            },
            {
                "title": "С чего начать разговор с поставщиком",
                "text": (
                    "Уточните стоимость ближайшего заказа и дату окончания "
                    "периода фиксации."
                ),
            },
        ],
    },
    {
        "id": "purchase-budget",
        "topic": "Финансы",
        "title": "Как проверить запас бюджета на материалы",
        "summary": (
            "Один сценарий изменения цены поможет увидеть, какую сумму стоит "
            "обсудить с финансовой командой."
        ),
        "minutes": 3,
        "cover": "budget",
        "sections": [
            {
                "title": "Проверьте одно допущение",
                "text": ("Выберите компанию, период и предполагаемое изменение цены."),
            },
            {
                "title": "Как получается сумма",
                "text": (
                    "Стоимость закупок без фиксации умножается на изменение цены."
                ),
            },
            {
                "title": "Что обсудить с финансовой командой",
                "text": ("Сравните получившуюся разницу с доступным бюджетом проекта."),
            },
        ],
    },
]


def find_user(user_id: str) -> DemoUser | None:
    return next((user for user in DEMO_USERS if user.id == user_id), None)


def find_insight(insight_id: str) -> dict | None:
    return next(
        (insight for insight in INSIGHTS if insight["id"] == insight_id),
        None,
    )

