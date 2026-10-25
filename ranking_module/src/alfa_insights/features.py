"""Feature engineering: compute missing columns + company/news profiles for hard recall."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .config import FeaturesConfig

log = logging.getLogger(__name__)

PRODUCTS = ["RKO", "GAR", "LOA", "LEA", "DEP", "ZPP"]


@dataclass
class CompanyProfile:
    id: str | None = None
    name: str | None = None
    aliases: list[str] = field(default_factory=list)
    domain: str | None = None
    okved_class: str | None = None
    okved_name: str | None = None
    okved_sector: str | None = None
    region: str | None = None
    city: str | None = None
    worker_ord: int | None = None
    binary_sum_products: int | None = None
    cl_type: str | None = None
    group_id: str | None = None
    industry_freq: float | None = None
    revenue_rank_industry: float | None = None
    specialization: str | None = None


@dataclass
class NewsSignals:
    item_id: str | None = None
    sectors: set[str] = field(default_factory=set)
    regions: set[str] = field(default_factory=set)
    products: set[str] = field(default_factory=set)
    worker_levels: set[int] = field(default_factory=set)
    entity_names: set[str] = field(default_factory=set)
    entity_domains: set[str] = field(default_factory=set)


_SECTOR_KEYWORDS = {
    "trade": ["торговля", "оптовая", "розничная", "ритейл", "магазин"],
    "manufacturing": ["производство", "завод", "промышлен", "изготовлен", "робот"],
    "construction": ["строительств", "стройка", "подрядчик"],
    "finance": ["банк", "финанс", "страхован", "лизинг"],
    "real_estate": ["недвижим", "аренда", "девелопер"],
    "services": ["услуг", "сервис", "обслуживан"],
}

_PRODUCT_KEYWORDS = {
    "RKO": ["расчетн", "рко", "счет"],
    "GAR": ["гарант", "банковская гарантия"],
    "LOA": ["кредит", "кредитован", "займ"],
    "LEA": ["лизинг"],
    "DEP": ["депозит", "вклад"],
    "ZPP": ["зарплат", "зарплатный проект"],
}

_REGION_KEYWORDS = [
    "москва",
    "санкт-петербург",
    "новосибирск",
    "екатеринбург",
    "челябинск",
    "курган",
    "барнаул",
    "нижний новгород",
    "тюмень",
    "ижевск",
    "мурманск",
    "уфа",
    "алтайский край",
    "свердловская область",
    "челябинская область",
    "курганская область",
    "тюменская область",
    "удмуртская республика",
    "мурманская область",
    "башкортостан",
    "нижегородская область",
]


def _okved_class(code: Any) -> str | None:
    if code is None or (isinstance(code, float) and np.isnan(code)):
        return None
    s = str(code).strip()
    if not s:
        return None
    return s[:2]


def _okved_sector(okved_class: str | None, cfg: FeaturesConfig) -> str | None:
    if not okved_class:
        return None
    try:
        cls = int(okved_class)
    except ValueError:
        return None
    for sector, codes in cfg.okved_sector_map.items():
        if cls in codes:
            return sector
    return "services"


def _age_ord(age_mid: float | None, thresholds: list[int]) -> int | None:
    if age_mid is None or (isinstance(age_mid, float) and np.isnan(age_mid)):
        return None
    # thresholds ascending: [3,5,10,20] -> ord 1..5
    for i, t in enumerate(thresholds):
        if age_mid < t:
            return i + 1
    return len(thresholds) + 1


def build_features(df: pd.DataFrame, cfg: FeaturesConfig, force: bool = False) -> pd.DataFrame:
    """Compute missing feature columns from description. Idempotent unless force=True."""
    out = df.copy()

    # age_ord
    if force or "age_ord" not in out.columns:
        out["age_ord"] = out.get("age_mid", pd.Series([None] * len(out))).apply(
            lambda v: _age_ord(v, cfg.age_ord_thresholds)
        )

    # product sums if absent
    product_cols = [f"CL_PRODUCT_{p}_MARK" for p in PRODUCTS]
    existing = [c for c in product_cols if c in out.columns]
    if existing and (force or "binary_sum_products" not in out.columns):
        out["binary_sum_products"] = out[existing].fillna(0).sum(axis=1).astype("Int8")

    # deep_client: (LOA|LEA|DEP) & (RKO|ZPP|GAR)
    if force or "deep_client" not in out.columns:

        def _deep(row: pd.Series) -> int:
            fin = any(row.get(f"CL_PRODUCT_{p}_MARK", 0) == 1 for p in ("LOA", "LEA", "DEP"))
            trx = any(row.get(f"CL_PRODUCT_{p}_MARK", 0) == 1 for p in ("RKO", "ZPP", "GAR"))
            return int(fin and trx)

        out["deep_client"] = out.apply(_deep, axis=1)

    # small_with_many: worker_ord==1 & binary_sum_products>=3
    if force or "small_with_many" not in out.columns:
        wo = pd.to_numeric(out.get("worker_ord"), errors="coerce")
        bs = pd.to_numeric(out.get("binary_sum_products"), errors="coerce")
        out["small_with_many"] = ((wo == 1) & (bs >= 3)).astype(int)

    # okved_sector
    if force or "okved_sector" not in out.columns:
        okved = out.get("okved_class")
        if okved is None and "MAINOKVED_CODE" in out.columns:
            okved = out["MAINOKVED_CODE"].apply(_okved_class)
        out["okved_sector"] = (
            okved.apply(lambda v: _okved_sector(v, cfg)) if okved is not None else None
        )

    # industry_freq
    if force or "industry_freq" not in out.columns:
        if "okved_class" in out.columns:
            vc = out["okved_class"].value_counts(normalize=True)
            out["industry_freq"] = out["okved_class"].map(vc)
        else:
            out["industry_freq"] = np.nan

    # revenue_rank_industry
    if force or "revenue_rank_industry" not in out.columns:
        if "okved_class" in out.columns and "REVENUE_COMPANY" in out.columns:
            out["revenue_rank_industry"] = out.groupby("okved_class")["REVENUE_COMPANY"].rank(
                pct=True
            )
        else:
            out["revenue_rank_industry"] = np.nan

    # industry_client_share
    if force or "industry_client_share" not in out.columns:
        if "okved_class" in out.columns and "CL_TYPE" in out.columns:
            is_client = out["CL_TYPE"].isin(["CLIENT", "CLOSE_CLIENT"]).astype(int)
            share = is_client.groupby(out["okved_class"]).transform("mean")
            out["industry_client_share"] = share
        else:
            out["industry_client_share"] = np.nan

    # okved_share_<PRODUCT>
    for p in PRODUCTS:
        col = f"okved_share_{p}"
        src = f"CL_PRODUCT_{p}_MARK"
        if src in out.columns and (force or col not in out.columns):
            if "okved_class" in out.columns:
                out[col] = out.groupby("okved_class")[src].transform("mean")
            else:
                out[col] = np.nan

    # revenue_per_worker
    if force or "revenue_per_worker" not in out.columns:
        w = pd.to_numeric(out.get("worker_mid_approx"), errors="coerce").replace(0, np.nan)
        r = pd.to_numeric(out.get("REVENUE_COMPANY"), errors="coerce")
        out["revenue_per_worker"] = (r / w).astype(float)

    # group features
    if force or "is_group_member" not in out.columns:
        if "GROUP_ID" in out.columns:
            out["is_group_member"] = out["GROUP_ID"].notna().astype(int)
        else:
            out["is_group_member"] = 0

    if force or "group_size" not in out.columns:
        if "GROUP_ID" in out.columns and "SYNTHETIC_U" in out.columns:
            sizes = out.groupby("GROUP_ID")["SYNTHETIC_U"].transform("nunique")
            out["group_size"] = sizes.fillna(1)
        else:
            out["group_size"] = 1

    if force or "company_share_group_revenue" not in out.columns:
        if "GROUP_ID" in out.columns and "REVENUE_COMPANY" in out.columns:
            total = out.groupby("GROUP_ID")["REVENUE_COMPANY"].transform("sum")
            out["company_share_group_revenue"] = out["REVENUE_COMPANY"] / total.replace(0, np.nan)
        else:
            out["company_share_group_revenue"] = np.nan

    # region features
    if force or "region_company_count" not in out.columns:
        if "REGION" in out.columns and "SYNTHETIC_U" in out.columns:
            out["region_company_count"] = out.groupby("REGION")["SYNTHETIC_U"].transform("nunique")
        else:
            out["region_company_count"] = np.nan

    if force or "region_revenue_share" not in out.columns:
        if "REGION" in out.columns and "REVENUE_COMPANY" in out.columns:
            total = out.groupby("REGION")["REVENUE_COMPANY"].transform("sum")
            out["region_revenue_share"] = out["REVENUE_COMPANY"] / total.replace(0, np.nan)
        else:
            out["region_revenue_share"] = np.nan

    if force or "n_regions_in_group" not in out.columns:
        if "GROUP_ID" in out.columns and "REGION" in out.columns:
            n = out.dropna(subset=["GROUP_ID"]).groupby("GROUP_ID")["REGION"].transform("nunique")
            out["n_regions_in_group"] = n.reindex(out.index).fillna(1)
        else:
            out["n_regions_in_group"] = 1

    return out


def company_profile(row: pd.Series, watch: Any | None = None) -> CompanyProfile:
    """Build CompanyProfile from a dataframe row and optional WatchItem."""
    return CompanyProfile(
        id=watch.id
        if watch is not None
        else (row.get("SYNTHETIC_U") if hasattr(row, "get") else None),
        name=watch.name if watch is not None else None,
        aliases=list(watch.aliases) if watch is not None else [],
        domain=watch.domain if watch is not None else None,
        okved_class=_okved_class(row.get("MAINOKVED_CODE")) if hasattr(row, "get") else None,
        okved_name=row.get("MAINOKVED_NAME") if hasattr(row, "get") else None,
        okved_sector=row.get("okved_sector") if hasattr(row, "get") else None,
        region=row.get("REGION") if hasattr(row, "get") else None,
        city=row.get("CITY") if hasattr(row, "get") else None,
        worker_ord=int(row["worker_ord"])
        if hasattr(row, "get") and pd.notna(row.get("worker_ord"))
        else None,
        binary_sum_products=int(row["binary_sum_products"])
        if hasattr(row, "get") and pd.notna(row.get("binary_sum_products"))
        else None,
        cl_type=row.get("CL_TYPE") if hasattr(row, "get") else None,
        group_id=row.get("GROUP_ID") if hasattr(row, "get") else None,
        industry_freq=float(row["industry_freq"])
        if hasattr(row, "get") and pd.notna(row.get("industry_freq"))
        else None,
        revenue_rank_industry=float(row["revenue_rank_industry"])
        if hasattr(row, "get") and pd.notna(row.get("revenue_rank_industry"))
        else None,
        specialization=watch.specialization if watch is not None else None,
    )


def news_signals(item: Any) -> NewsSignals:
    """Extract sector/region/product signals from a news/pdf item."""
    text = " ".join(
        filter(None, [getattr(item, "title", "") or "", getattr(item, "text", "") or ""])
    ).lower()
    sectors = {s for s, kws in _SECTOR_KEYWORDS.items() if any(k in text for k in kws)}
    regions = {r for r in _REGION_KEYWORDS if r in text}
    products = {p for p, kws in _PRODUCT_KEYWORDS.items() if any(k in text for k in kws)}
    levels = set()
    if any(w in text for w in ["мал", "микро", "стартап"]):
        levels.add(1)
    if "средн" in text:
        levels.add(2)
    if any(w in text for w in ["крупн", "корпорац", "холдинг"]):
        levels.add(4)
    ems = getattr(item, "entity_matches", []) or []
    names = {(e.name or "").lower() for e in ems if getattr(e, "name", None)}
    domains = {(e.domain or "").lower() for e in ems if getattr(e, "domain", None)}
    return NewsSignals(
        item_id=getattr(item, "item_id", None),
        sectors=sectors,
        regions=regions,
        products=products,
        worker_levels=levels,
        entity_names=names,
        entity_domains=domains,
    )
