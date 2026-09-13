"""Pure calculation engine for qualitative coding coverage metrics.

Computes descriptive coverage statistics for a qualitative coding artifact:
- Coded vs uncoded row counts and percentages.
- Codes-per-row distribution (0, 1, 2, 3+ codes; min, max, mean, median).
- Code family rollups (aggregated entry counts and row frequencies by family_name/family_uid).
- Code density buckets (rows grouped by intensity of codes).

All metrics are computed deterministically from existing ``coding_entries``
and corpus row counts, with division-by-zero guards for empty/uncoded datasets.

IMPORTANT: These are purely descriptive coverage metrics of the sample corpus.
They quantify annotation distribution across rows in this artifact and do NOT imply
statistical representativeness or population inference.
"""

from __future__ import annotations

from typing import Any
import statistics

COVERAGE_DISCLAIMER_NOTICE = (
    "Descriptive coverage metrics of the sample corpus. These metrics quantify "
    "annotation distribution across rows in this artifact and do not imply "
    "statistical representativeness or population inference."
)


def _get_field(obj: Any, field: str, default: Any = None) -> Any:
    """Read a field from either a dict or an object attribute."""
    if isinstance(obj, dict):
        return obj.get(field, default)
    return getattr(obj, field, default)


def _safe_percentage(numerator: int, denominator: int, decimals: int = 2) -> float:
    """Safely calculate percentage avoiding division by zero."""
    if denominator <= 0 or numerator <= 0:
        return 0.0
    val = (numerator / denominator) * 100.0
    return round(val, decimals)


def compute_coverage_metrics(
    *,
    total_rows: int,
    entries: list[Any],
    codes: list[Any] | None = None,
) -> dict[str, Any]:
    """Compute deterministic coverage metrics from entries and row counts.

    Parameters:
        total_rows: Total number of rows in the corpus artifact.
        entries: CodingEntry instances or dicts (carrying row_type, post_id, code, code_uid).
        codes: CodebookCode instances or dicts (carrying code_uid, name, family_uid, family_name).

    Returns:
        A dictionary containing:
        - total_rows, coded_rows, uncoded_rows, coded_percentage, uncoded_percentage
        - total_entries, distinct_codes_applied, total_codebook_codes
        - codes_per_row: distribution, percentages, min, max, mean, median, coded_only stats
        - density_buckets: list of buckets (0 codes, 1 code, 2 codes, 3-4 codes, 5+ codes)
        - family_rollups: list of family rollups with nested code breakdowns
        - notice: descriptive disclaimer
    """
    total_rows = max(0, int(total_rows or 0))

    # 1. Build codebook snapshot lookup
    # Map code_uid -> {code_uid, name, family_uid, family_name, position}
    code_lookup: dict[str, dict[str, Any]] = {}
    family_meta: dict[str, dict[str, Any]] = {}
    family_order: list[str] = []

    for c in codes or []:
        c_uid = str(_get_field(c, "code_uid") or "").strip()
        if not c_uid:
            continue
        c_name = str(_get_field(c, "name") or "").strip()
        f_uid = str(_get_field(c, "family_uid") or "unassigned").strip() or "unassigned"
        f_name = str(_get_field(c, "family_name") or "Unassigned").strip() or "Unassigned"
        pos = int(_get_field(c, "position") or 0)

        code_lookup[c_uid] = {
            "code_uid": c_uid,
            "name": c_name,
            "family_uid": f_uid,
            "family_name": f_name,
            "position": pos,
        }

        if f_uid not in family_meta:
            family_meta[f_uid] = {
                "family_uid": f_uid,
                "family_name": f_name,
                "position": pos,
                "codes": {},
            }
            family_order.append(f_uid)
        family_meta[f_uid]["codes"][c_uid] = {
            "code_uid": c_uid,
            "name": c_name,
            "position": pos,
            "entry_count": 0,
            "row_keys": set(),
        }

    # 2. Process coding entries
    row_distinct_codes: dict[tuple[str, str], set[str]] = {}
    row_entry_counts: dict[tuple[str, str], int] = {}
    distinct_codes_applied: set[str] = set()

    # Track family stats
    family_entries: dict[str, int] = {f_uid: 0 for f_uid in family_order}
    family_rows: dict[str, set[tuple[str, str]]] = {f_uid: set() for f_uid in family_order}

    for entry in entries or []:
        r_type = str(_get_field(entry, "row_type") or "submission").strip()
        p_id = str(_get_field(entry, "post_id") or "").strip()
        if not p_id:
            continue
        row_key = (r_type, p_id)

        c_uid = str(_get_field(entry, "code_uid") or "").strip()
        c_name = str(_get_field(entry, "code") or "").strip()

        # Resolve code and family metadata
        if c_uid and c_uid in code_lookup:
            meta = code_lookup[c_uid]
            resolved_c_uid = c_uid
            resolved_c_name = meta["name"]
            f_uid = meta["family_uid"]
            f_name = meta["family_name"]
        else:
            resolved_c_uid = c_uid or c_name or "unknown"
            resolved_c_name = c_name or resolved_c_uid
            f_uid = "unassigned"
            f_name = "Unassigned"

        distinct_codes_applied.add(resolved_c_uid)
        row_distinct_codes.setdefault(row_key, set()).add(resolved_c_uid)
        row_entry_counts[row_key] = row_entry_counts.get(row_key, 0) + 1

        # Register unassigned family dynamically if needed
        if f_uid not in family_meta:
            family_meta[f_uid] = {
                "family_uid": f_uid,
                "family_name": f_name,
                "position": 999999,
                "codes": {},
            }
            family_order.append(f_uid)
            family_entries[f_uid] = 0
            family_rows[f_uid] = set()

        if resolved_c_uid not in family_meta[f_uid]["codes"]:
            family_meta[f_uid]["codes"][resolved_c_uid] = {
                "code_uid": resolved_c_uid,
                "name": resolved_c_name,
                "position": 999999,
                "entry_count": 0,
                "row_keys": set(),
            }

        family_entries[f_uid] = family_entries.get(f_uid, 0) + 1
        family_rows[f_uid].add(row_key)

        code_entry = family_meta[f_uid]["codes"][resolved_c_uid]
        code_entry["entry_count"] += 1
        code_entry["row_keys"].add(row_key)

    # 3. Overall coded vs uncoded counts
    coded_rows = len(row_distinct_codes)
    effective_total_rows = max(total_rows, coded_rows)
    uncoded_rows = max(0, effective_total_rows - coded_rows)

    coded_pct = _safe_percentage(coded_rows, effective_total_rows)
    uncoded_pct = _safe_percentage(uncoded_rows, effective_total_rows)

    # 4. Codes-per-row distribution and summary statistics
    # Distribution buckets: 0, 1, 2, 3+ distinct codes
    count_0 = uncoded_rows
    count_1 = sum(1 for c_set in row_distinct_codes.values() if len(c_set) == 1)
    count_2 = sum(1 for c_set in row_distinct_codes.values() if len(c_set) == 2)
    count_3_plus = sum(1 for c_set in row_distinct_codes.values() if len(c_set) >= 3)

    codes_per_row_distribution = {
        "0": count_0,
        "1": count_1,
        "2": count_2,
        "3+": count_3_plus,
    }
    codes_per_row_percentages = {
        "0": _safe_percentage(count_0, effective_total_rows),
        "1": _safe_percentage(count_1, effective_total_rows),
        "2": _safe_percentage(count_2, effective_total_rows),
        "3+": _safe_percentage(count_3_plus, effective_total_rows),
    }

    all_row_counts = [0] * uncoded_rows + [len(c_set) for c_set in row_distinct_codes.values()]
    if effective_total_rows > 0 and all_row_counts:
        stat_min = min(all_row_counts)
        stat_max = max(all_row_counts)
        stat_mean = round(sum(all_row_counts) / effective_total_rows, 2)
        stat_median = float(round(statistics.median(all_row_counts), 2))
    else:
        stat_min = 0
        stat_max = 0
        stat_mean = 0.0
        stat_median = 0.0

    coded_row_counts = [len(c_set) for c_set in row_distinct_codes.values()]
    if coded_row_counts:
        coded_min = min(coded_row_counts)
        coded_max = max(coded_row_counts)
        coded_mean = round(sum(coded_row_counts) / len(coded_row_counts), 2)
        coded_median = float(round(statistics.median(coded_row_counts), 2))
    else:
        coded_min = 0
        coded_max = 0
        coded_mean = 0.0
        coded_median = 0.0

    # 5. Density buckets: grouped by intensity of codes
    count_3_4 = sum(1 for c_set in row_distinct_codes.values() if len(c_set) in (3, 4))
    count_5_plus = sum(1 for c_set in row_distinct_codes.values() if len(c_set) >= 5)

    density_buckets = [
        {
            "bucket": "0 codes",
            "label": "Uncoded",
            "min_codes": 0,
            "max_codes": 0,
            "row_count": count_0,
            "percentage": _safe_percentage(count_0, effective_total_rows),
        },
        {
            "bucket": "1 code",
            "label": "Single code",
            "min_codes": 1,
            "max_codes": 1,
            "row_count": count_1,
            "percentage": _safe_percentage(count_1, effective_total_rows),
        },
        {
            "bucket": "2 codes",
            "label": "Dual codes",
            "min_codes": 2,
            "max_codes": 2,
            "row_count": count_2,
            "percentage": _safe_percentage(count_2, effective_total_rows),
        },
        {
            "bucket": "3-4 codes",
            "label": "Moderate density",
            "min_codes": 3,
            "max_codes": 4,
            "row_count": count_3_4,
            "percentage": _safe_percentage(count_3_4, effective_total_rows),
        },
        {
            "bucket": "5+ codes",
            "label": "High density",
            "min_codes": 5,
            "max_codes": None,
            "row_count": count_5_plus,
            "percentage": _safe_percentage(count_5_plus, effective_total_rows),
        },
    ]

    # 6. Code family rollups
    family_rollups = []
    for f_uid in family_order:
        f_info = family_meta[f_uid]
        f_row_set = family_rows.get(f_uid, set())
        f_row_count = len(f_row_set)
        f_entry_count = family_entries.get(f_uid, 0)

        codes_in_fam = []
        for c_data in f_info["codes"].values():
            c_rows = len(c_data["row_keys"])
            codes_in_fam.append(
                {
                    "code_uid": c_data["code_uid"],
                    "name": c_data["name"],
                    "position": c_data["position"],
                    "entry_count": c_data["entry_count"],
                    "row_count": c_rows,
                    "row_percentage": _safe_percentage(c_rows, effective_total_rows),
                }
            )

        # Sort codes inside family by row_count desc, entry_count desc, position asc
        codes_in_fam.sort(key=lambda x: (-x["row_count"], -x["entry_count"], x["position"], x["name"]))

        family_rollups.append(
            {
                "family_uid": f_uid,
                "family_name": f_info["family_name"],
                "position": f_info["position"],
                "entry_count": f_entry_count,
                "row_count": f_row_count,
                "row_percentage": _safe_percentage(f_row_count, effective_total_rows),
                "codes": codes_in_fam,
            }
        )

    # Sort families by row_count desc, entry_count desc, position asc
    family_rollups.sort(key=lambda x: (-x["row_count"], -x["entry_count"], x["position"], x["family_name"]))

    return {
        "total_rows": effective_total_rows,
        "coded_rows": coded_rows,
        "uncoded_rows": uncoded_rows,
        "coded_percentage": coded_pct,
        "uncoded_percentage": uncoded_pct,
        "total_entries": len(entries or []),
        "distinct_codes_applied": len(distinct_codes_applied),
        "total_codebook_codes": len(code_lookup),
        "codes_per_row": {
            "distribution": codes_per_row_distribution,
            "percentages": codes_per_row_percentages,
            "min": stat_min,
            "max": stat_max,
            "mean": stat_mean,
            "median": stat_median,
            "coded_only": {
                "min": coded_min,
                "max": coded_max,
                "mean": coded_mean,
                "median": coded_median,
            },
        },
        "density_buckets": density_buckets,
        "family_rollups": family_rollups,
        "notice": COVERAGE_DISCLAIMER_NOTICE,
    }
