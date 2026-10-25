"""Notebook cells 13, 14, 21, 29 and feature formulas in cells 42–43."""
from bisect import bisect_right
from collections import Counter, defaultdict
import math
import re
from .cleaning import PRODUCTS, WORKER_ORD, WORKER_MID

VARIABLE_PRODUCTS = ("GAR", "LOA", "LEA", "DEP")


def divide(numerator, denominator):
    return numerator / denominator if numerator is not None and denominator not in (None, 0) else None


def sector(code):
    if code is None:
        return None
    number = int(code)
    if number in (45, 46, 47):
        return "торговля"
    if 5 <= number <= 33:
        return "производство"
    if number in (41, 42, 43):
        return "строительство"
    if number in (64, 65, 66):
        return "финансы"
    if number == 68:
        return "недвижимость"
    return "услуги"


def build_features(records):
    industries, groups, regions = defaultdict(list), defaultdict(list), defaultdict(list)
    for record in records:
        row = record["attributes"]
        match = re.match(r"^(\d{2})(?:\.|$)", row["MAINOKVED_CODE"] or "")
        code = match[1] if match else None
        age = re.search(r"(\d+)\s*[-–]\s*(\d+)", row["COMPANY_AGE_YEARS_GRADATION"] or "")
        lo, hi = (int(age[1]), int(age[2])) if age else (None, None)
        if lo is not None and lo > hi:
            lo, hi = None, None
            record["warnings"].append("Invalid age interval")
        mid = (lo + hi) / 2 if lo is not None else None
        worker = row["AMOUNT_WORKERS_FNS_GRADATION"]
        revenue = row["REVENUE_COMPANY"]
        # The case clarifications identify 1000 as a placeholder. Keep the raw value but exclude it from metrics.
        revenue = None if revenue == 1000 else revenue
        if revenue is not None and revenue < 0:
            record["warnings"].append("Negative revenue: clipped to zero only for revenue_log")
        products = [row[column] for column in PRODUCTS]
        if any(value is None for value in products):
            record["warnings"].append("Product count uses zero for unknown flags, following the notebook")
        product_count = sum(value or 0 for value in products)
        features = {
            "worker_ord": WORKER_ORD.get(worker), "worker_mid_approx": WORKER_MID.get(worker),
            "age_lo": lo, "age_hi": hi, "age_mid": mid,
            "age_ord": bisect_right((3, 5, 10, 20), mid) + 1 if mid is not None else None,
            "revenue_log": math.log1p(max(revenue, 0)) if revenue is not None else None,
            "binary_sum_products": product_count,
            "deep_client": int(any(row[f"CL_PRODUCT_{p}_MARK"] == 1 for p in ("LOA","LEA","DEP"))
                               and any(row[f"CL_PRODUCT_{p}_MARK"] == 1 for p in ("RKO","ZPP","GAR"))),
            "small_with_many": int(WORKER_ORD.get(worker) == 1 and product_count >= 3),
            "okved_class": code, "okved_sector": sector(code),
            "revenue_per_worker": divide(revenue, WORKER_MID.get(worker)),
            "is_group_member": int(bool(row["GROUP_ID"])),
        }
        if code is None:
            record["warnings"].append("Missing or invalid OKVED code")
        if worker and worker not in WORKER_ORD:
            record["warnings"].append("Unknown worker category")
        record.update(company_id=row["SYNTHETIC_U"], industry=row["MAINOKVED_NAME"],
                      okved_code=row["MAINOKVED_CODE"], region=row["REGION"], city=row["CITY"],
                      group_id=row["GROUP_ID"], client_type=row["CL_TYPE"], features=features)
        record["_revenue"] = revenue
        if code is not None:
            industries[code].append(record)
        if row["GROUP_ID"]:
            groups[row["GROUP_ID"]].append(record)
        if row["REGION"]:
            regions[row["REGION"]].append(record)
    for code, members in industries.items():
        counts = Counter(r["_revenue"] for r in members if r["_revenue"] is not None)
        rank, ranks = 1, {}
        total_ranked = sum(counts.values())
        for value, count in sorted(counts.items()):
            ranks[value] = (rank + (count - 1) / 2) / total_ranked
            rank += count
        shares = {}
        for product in VARIABLE_PRODUCTS:
            values = [r["attributes"][f"CL_PRODUCT_{product}_MARK"] for r in members
                      if r["attributes"][f"CL_PRODUCT_{product}_MARK"] is not None]
            shares[product] = sum(values) / len(values) if values else None
        client_share = sum(r["client_type"] in {"CLIENT", "CLOSE_CLIENT"} for r in members) / len(members)
        for record in members:
            record["features"].update(industry_freq=len(members)/len(records),
                                      revenue_rank_industry=ranks.get(record["_revenue"]),
                                      industry_client_share=client_share,
                                      **{f"okved_share_{p}": value for p, value in shares.items()})
    for record in records:
        features = record["features"]
        for key in ("industry_freq", "revenue_rank_industry", "industry_client_share",
                    *(f"okved_share_{p}" for p in VARIABLE_PRODUCTS)):
            features.setdefault(key, None)
    for members in groups.values():
        revenue = sum(r["_revenue"] for r in members if r["_revenue"] is not None)
        group_regions = sorted({r["region"] for r in members if r["region"]})
        group_industries = sorted({r["industry"] for r in members if r["industry"]})
        for record in members:
            record["features"].update(group_size=len(members),
                                      company_share_group_revenue=divide(record["_revenue"], revenue),
                                      n_regions_in_group=len(group_regions))
            record["group_context"] = {"industries": group_industries, "regions": group_regions}
    for members in regions.values():
        revenue = sum(r["_revenue"] for r in members if r["_revenue"] is not None)
        for record in members:
            record["features"].update(region_company_count=len(members),
                                      region_revenue_share=divide(record["_revenue"], revenue))
    for record in records:
        features = record["features"]
        features.setdefault("group_size", 1)
        features.setdefault("company_share_group_revenue", None)
        features.setdefault("n_regions_in_group", 1)
        features.setdefault("region_company_count", None)
        features.setdefault("region_revenue_share", None)
        record.setdefault("group_context", {"industries": [record["industry"]] if record["industry"] else [],
                                           "regions": [record["region"]] if record["region"] else []})
        del record["_revenue"]
    return records
