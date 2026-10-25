"""Notebook cells 5–14: identity audit, business deduplication, missing values."""
from collections import Counter, defaultdict
import math
import re

PRODUCTS = tuple(f"CL_PRODUCT_{name}_MARK" for name in ("RKO", "GAR", "LOA", "LEA", "DEP", "ZPP"))
BINARY_FLAGS = PRODUCTS + ("NEGATIVEMARK", "FTS_FLAG", "FACTORING_MARK")
WORKER_ORD = {"Менее 15": 1, "16-100": 2, "101-250": 3, "Более 251": 4}
WORKER_MID = {"Менее 15": 7, "16-100": 58, "101-250": 175, "Более 251": 251}
REQUIRED = {
    "SYNTHETIC_U", "GROUP_ID", "CL_TYPE", "MAINOKVED_CODE", "MAINOKVED_NAME",
    "REGION", "CITY", "COMPANY_AGE_YEARS_GRADATION", "REVENUE_COMPANY",
    "AMOUNT_WORKERS_FNS_GRADATION", "FTS_COUNTRY_NAME", "ECO_MARK_LABEL",
    *BINARY_FLAGS,
}


def numeric(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def clean_rows(rows):
    records = []
    counts = Counter()
    groups = defaultdict(list)
    max_id = 0
    for line, row in rows:
        missing = REQUIRED - row.keys()
        if missing:
            raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
        uid = row["SYNTHETIC_U"]
        if not uid or not re.fullmatch(r"U_\d+", uid):
            raise ValueError(f"Invalid SYNTHETIC_U at source line {line}: {uid!r}")
        max_id = max(max_id, int(uid[2:]))
        groups[uid].append(len(records))
        records.append({"source_row": line, "source_company_id": uid, "attributes": row,
                        "warnings": [], "identity_ambiguous": False})
    renamed = []
    for uid, indices in groups.items():
        if len(indices) < 2:
            continue
        for index in indices:
            records[index]["identity_ambiguous"] = True
            records[index]["warnings"].append(
                "Source company ID collides; payment/person links cannot be resolved by this ID.")
        for index in indices[1:]:
            max_id += 1
            new_id = f"U_{max_id}"
            records[index]["attributes"]["SYNTHETIC_U"] = new_id
            renamed.append({"source_row": records[index]["source_row"],
                            "source_company_id": uid, "company_id": new_id})
    seen, clean, removed = {}, [], []
    for record in records:
        row = record["attributes"]
        # The notebook excludes GROUP_ID as well as the identifier from business deduplication.
        signature = tuple(
            (key, numeric(row[key]) if key in (*BINARY_FLAGS, "REVENUE_COMPANY")
             and numeric(row[key]) is not None else row[key])
            for key in sorted(row) if key not in {"SYNTHETIC_U", "GROUP_ID"}
        )
        if signature in seen:
            removed.append({"source_row": record["source_row"], "company_id": row["SYNTHETIC_U"],
                            "group_id": row["GROUP_ID"], "retained_company_id": seen[signature]})
            continue
        seen[signature] = row["SYNTHETIC_U"]
        row.pop("AMOUNT_WORKERS_SPARK_GRADATION", None)
        row["FTS_COUNTRY_NAME"] = row["FTS_COUNTRY_NAME"] or "НЕТ_ВЭД"
        row["ECO_MARK_LABEL"] = row["ECO_MARK_LABEL"] or "НЕ_ОПРЕДЕЛЕНО"
        for column in BINARY_FLAGS:
            value = numeric(row[column])
            if value not in (0, 1, None):
                record["warnings"].append(f"{column}: non-binary value treated as unknown")
                value = None
            elif row[column] is not None and value is None:
                record["warnings"].append(f"{column}: invalid number treated as unknown")
            row[column] = int(value) if value is not None else None
        original_revenue = row["REVENUE_COMPANY"]
        row["REVENUE_COMPANY"] = numeric(original_revenue)
        if original_revenue is not None and row["REVENUE_COMPANY"] is None:
            record["warnings"].append("Invalid revenue treated as unknown")
        if row["REVENUE_COMPANY"] == 1000:
            record["warnings"].append("Revenue 1000 is an unknown-value placeholder under case clarifications")
        counts.update(key for key, value in row.items() if value is None)
        clean.append(record)
    audit = {
        "rows_read": len(records), "rows_clean": len(clean),
        "source_id_collisions": {uid: len(indices) for uid, indices in groups.items() if len(indices) > 1},
        "renamed_ids": renamed, "business_duplicates_removed": removed,
        "missing_after_cleaning": dict(counts),
        "notes": [
            "Business duplicates exclude SYNTHETIC_U and GROUP_ID; the first row is retained.",
            "ID renaming is local to profiles; ambiguous IDs are never remapped into payment/person tables.",
            "No payment or physical-person-link preprocessing is defined in the supplied notebook.",
        ],
    }
    return clean, audit
