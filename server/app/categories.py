"""One adapter from ML's canonical category IDs to the ten SVG assets."""
import json
from pathlib import Path
from insides.categories import CATEGORIES as ML_CATEGORIES

ASSETS_DIR = Path(__file__).resolve().parent.parent / 'static'
_assets = json.loads((ASSETS_DIR / 'insight-categories' / 'manifest.json').read_text())
# Explicit association: never infer an image from the article title or list position.
ASSET_IDS = {
    1: 'finance-rates', 2: 'currencies-payments', 3: 'commodities-energy',
    4: 'demand-consumption', 5: 'logistics-supplies', 6: 'competition-market',
    7: 'regulation-taxes', 8: 'team-labor', 9: 'technology-risks', 10: 'investment-development',
}
_by_asset = {item['id']: item for item in _assets}
CATEGORIES = [{**item, 'asset_id': ASSET_IDS[item['id']],
               'cover_url': _by_asset[ASSET_IDS[item['id']]]['cover_url'],
               'cover_background': _by_asset[ASSET_IDS[item['id']]]['cover_background']}
              for item in ML_CATEGORIES]
CATEGORY_BY_ID = {item['id']: item for item in CATEGORIES}
_aliases = {str(value): item for item in CATEGORIES for value in (item['slug'], item['image_key'], item['asset_id'])}
LEGACY_CATEGORIES = {'steel': 3, 'contracts': 7, 'budget': 1}
INSIGHT_CATEGORIES = {'steel-cost': 3, 'price-fixation': 3, 'purchase-budget': 1}


def resolve_category(value):
    if type(value) is int:
        return CATEGORY_BY_ID.get(value)
    return _aliases.get(value) if isinstance(value, str) else None


def category_for_insight(insight):
    return resolve_category(insight.cover) or CATEGORY_BY_ID.get(INSIGHT_CATEGORIES.get(insight.id, LEGACY_CATEGORIES.get(insight.cover)))
