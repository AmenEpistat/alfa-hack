"""Trusted, versioned Alfa-Bank product catalog; no user-supplied URLs."""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

CATALOG_PATH = Path(__file__).with_name("alfa_products.json")


@lru_cache(maxsize=4)
def _parse_catalog(raw: bytes) -> dict:
    catalog = json.loads(raw)
    if catalog.get("schema_version") != "1.0" or not catalog.get("products"):
        raise ValueError("Invalid product catalog")
    seen = set()
    for product in catalog["products"]:
        if not all(isinstance(product.get(key), str) and product[key].strip()
                   for key in ("product_id", "name", "url", "description", "applicability")):
            raise ValueError("Product catalog entry is incomplete")
        parsed = urlsplit(product["url"])
        if (parsed.scheme != "https" or parsed.hostname != "alfabank.ru"
                or parsed.username or parsed.password or parsed.port not in (None, 443)
                or parsed.query or parsed.fragment):
            raise ValueError("Product links must use the official Alfa-Bank HTTPS domain")
        if product["product_id"] in seen:
            raise ValueError("Duplicate product ID")
        seen.add(product["product_id"])
    catalog["content_sha256"] = hashlib.sha256(raw).hexdigest()
    return catalog


def load_product_catalog() -> dict:
    # Hash actual bytes so same-size edits immediately invalidate generation cache.
    return deepcopy(_parse_catalog(CATALOG_PATH.read_bytes()))


PRODUCT_RULES = """
ПРОДУКТЫ АЛЬФА-БАНКА:
Содержимое product_catalog — отдельный справочник продуктов, не источник событий или позиция аналитиков.
Выбери минимум ОДИН и максимум три подходящих продукта для КАЖДОГО инсайта.
Выбирай по механизму решения описанной проблемы, а не по категории или рекламной привлекательности.
Если ни один продукт не подходит, не выдумывай связь: такой инсайт не должен приниматься,
исправь аналитический угол в пределах подтверждённых событий.
В product_recommendations передай product_id из каталога; название и URL подставит код.
problem — Claim с basis=model_inference, company_fields и цитатами событий ЭТОГО инсайта.
capability_quote — точная непустая подстрока description выбранного продукта.
mechanism объясняет, как указанная возможность помогает с problem; не пересказывай лозунги.
application — конкретный следующий шаг в пределах полномочий target_audience.
conditions — условия уместности продукта, включая applicability из каталога.
Не представляй условие как известный признак клиента. Не обещай одобрение, доходность,
тариф, комиссию, экономию, срок подключения или гарантированное устранение проблемы.
Не добавляй численные условия: каталог не содержит тарифов. Продукт — вариант решения,
а не уже подключённая услуга и не автоматически исполненная банковская операция.
"""
