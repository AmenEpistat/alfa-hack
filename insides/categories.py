"""Canonical business categories; independent of news/PDF/competitor source types."""
from copy import deepcopy

CATEGORIES = [
    {
        "id": 1,
        "slug": "finance_rates",
        "name": "Финансы и ставки",
        "description": "Ключевая ставка, кредиты, депозиты, облигации и стоимость финансирования.",
        "image_key": "coins_percent",
        "image_description": "Монеты и символ процента."
    },
    {
        "id": 2,
        "slug": "currencies_international_payments",
        "name": "Валюты и международные расчеты",
        "description": "Валютные курсы, трансграничные платежи и условия международных расчетов.",
        "image_key": "globe_currency_exchange",
        "image_description": "Глобус и обмен валют."
    },
    {
        "id": 3,
        "slug": "commodities_energy_costs",
        "name": "Сырье, энергия и издержки",
        "description": "Нефть, газ, металлы, золото, электроэнергия и себестоимость.",
        "image_key": "metal_barrel_lightning",
        "image_description": "Слиток металла, бочка и молния."
    },
    {
        "id": 4,
        "slug": "demand_consumption",
        "name": "Спрос и потребление",
        "description": "Покупательская активность, продажи, экономический рост и охлаждение рынка.",
        "image_key": "shopping_basket_chart",
        "image_description": "Корзина покупок и диаграмма."
    },
    {
        "id": 5,
        "slug": "logistics_supply",
        "name": "Логистика и поставки",
        "description": "Перевозки, склады, маршруты, сроки доставки и цепочки поставок.",
        "image_key": "containers_route",
        "image_description": "Контейнеры и маршрут между точками."
    },
    {
        "id": 6,
        "slug": "competitors_market",
        "name": "Конкуренты и рынок",
        "description": "Действия конкурентов, появление новых игроков, слияния и изменение конкурентной ситуации.",
        "image_key": "chess_companies",
        "image_description": "Компании в виде шахматных фигур."
    },
    {
        "id": 7,
        "slug": "regulation_taxes",
        "name": "Регулирование и налоги",
        "description": "Законы, налоги, лицензии, государственные требования и ограничения.",
        "image_key": "document_scales",
        "image_description": "Документ и весы."
    },
    {
        "id": 8,
        "slug": "workforce_labor_market",
        "name": "Команда и рынок труда",
        "description": "Зарплаты, нехватка кадров, найм, квалификация и производительность сотрудников.",
        "image_key": "people_briefcase",
        "image_description": "Группа людей и рабочий портфель."
    },
    {
        "id": 9,
        "slug": "technology_digital_risks",
        "name": "Технологии и цифровые риски",
        "description": "Автоматизация, ИИ, новые технологии, киберугрозы и цифровые сбои.",
        "image_key": "microchip_gear",
        "image_description": "Микрочип и шестеренка."
    },
    {
        "id": 10,
        "slug": "investment_growth",
        "name": "Инвестиции и развитие",
        "description": "Капитальные вложения, новые производства, расширение бизнеса и выход в новые регионы.",
        "image_key": "factory_network",
        "image_description": "Строящийся завод и разветвляющаяся сеть."
    }
]


def get_category(category_id):
    if type(category_id) is not int or not 1 <= category_id <= len(CATEGORIES):
        raise ValueError("category_id must be one integer from 1 to 10")
    return deepcopy(CATEGORIES[category_id - 1])


def category_prompt():
    lines = ["КАТЕГОРИЯ ИНСАЙТА:", "Верни category_id: ровно одно целое число от 1 до 10 из списка ниже."]
    lines.extend(f"{item['id']}. {item['name']} — {item['description']}" for item in CATEGORIES)
    lines.extend(["Выбирай по главному совместному выводу synthesis и механизму влияния на компанию.",
                  "Категория не зависит от типа источника news/pdf/competitors: новость конкурента о найме может относиться к рынку труда.",
                  "При пересечении тем выбери одну доминирующую категорию, не возвращай массив и не добавляй новые категории.",
                  "Конкуренты и рынок — изменение конкурентной ситуации; Инвестиции и развитие — инвестиционный проект или расширение как основной вывод.",
                  "Не распределяй категории поровну и не меняй содержание инсайта ради категории. Картинку и название подставит backend."])
    return "\n".join(lines)
