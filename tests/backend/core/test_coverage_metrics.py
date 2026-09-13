"""Unit tests for backend/app/core/coverage_metrics.py.

Validates pure calculation of descriptive corpus coverage metrics:
- Division-by-zero guards for 0-row and 0-code artifacts.
- Exact reconciliation of coded/uncoded row counts and percentages.
- Codes-per-row distribution and summary statistics.
- Code density buckets (0, 1, 2, 3-4, 5+).
- Family rollups with stable UID resolution and renamed code resilience.
- Descriptive disclaimer notice presence.
"""

from backend.app.core.coverage_metrics import (
    COVERAGE_DISCLAIMER_NOTICE,
    compute_coverage_metrics,
)


def test_empty_corpus():
    metrics = compute_coverage_metrics(total_rows=0, entries=[], codes=[])
    assert metrics["total_rows"] == 0
    assert metrics["coded_rows"] == 0
    assert metrics["uncoded_rows"] == 0
    assert metrics["coded_percentage"] == 0.0
    assert metrics["uncoded_percentage"] == 0.0
    assert metrics["total_entries"] == 0
    assert metrics["distinct_codes_applied"] == 0
    assert metrics["codes_per_row"]["mean"] == 0.0
    assert metrics["codes_per_row"]["median"] == 0.0
    assert metrics["codes_per_row"]["min"] == 0
    assert metrics["codes_per_row"]["max"] == 0
    assert metrics["notice"] == COVERAGE_DISCLAIMER_NOTICE
    assert len(metrics["density_buckets"]) == 5
    assert metrics["density_buckets"][0]["row_count"] == 0


def test_uncoded_corpus():
    codes = [{"code_uid": "u1", "name": "Alpha", "family_uid": "f1", "family_name": "Fam"}]
    metrics = compute_coverage_metrics(total_rows=5, entries=[], codes=codes)
    assert metrics["total_rows"] == 5
    assert metrics["coded_rows"] == 0
    assert metrics["uncoded_rows"] == 5
    assert metrics["coded_percentage"] == 0.0
    assert metrics["uncoded_percentage"] == 100.0
    assert metrics["codes_per_row"]["distribution"]["0"] == 5
    assert metrics["codes_per_row"]["distribution"]["1"] == 0
    assert metrics["density_buckets"][0]["row_count"] == 5
    assert metrics["density_buckets"][0]["percentage"] == 100.0


def test_partially_coded_corpus_and_density_buckets():
    codes = [
        {"code_uid": "c1", "name": "Code 1", "family_uid": "f1", "family_name": "Family A", "position": 1},
        {"code_uid": "c2", "name": "Code 2", "family_uid": "f1", "family_name": "Family A", "position": 2},
        {"code_uid": "c3", "name": "Code 3", "family_uid": "f2", "family_name": "Family B", "position": 3},
        {"code_uid": "c4", "name": "Code 4", "family_uid": "f2", "family_name": "Family B", "position": 4},
        {"code_uid": "c5", "name": "Code 5", "family_uid": "f2", "family_name": "Family B", "position": 5},
    ]
    # 5 rows total:
    # row 1: c1 (1 code)
    # row 2: c1, c2 (2 codes)
    # row 3: c1, c2, c3 (3 codes -> 3-4 bucket)
    # row 4: c1, c2, c3, c4, c5 (5 codes -> 5+ bucket)
    # row 5: uncoded (0 codes)
    entries = [
        {"row_type": "submission", "post_id": "r1", "code_uid": "c1", "code": "Code 1"},
        {"row_type": "submission", "post_id": "r2", "code_uid": "c1", "code": "Code 1"},
        {"row_type": "submission", "post_id": "r2", "code_uid": "c2", "code": "Code 2"},
        {"row_type": "submission", "post_id": "r3", "code_uid": "c1", "code": "Code 1"},
        {"row_type": "submission", "post_id": "r3", "code_uid": "c2", "code": "Code 2"},
        {"row_type": "submission", "post_id": "r3", "code_uid": "c3", "code": "Code 3"},
        {"row_type": "submission", "post_id": "r4", "code_uid": "c1", "code": "Code 1"},
        {"row_type": "submission", "post_id": "r4", "code_uid": "c2", "code": "Code 2"},
        {"row_type": "submission", "post_id": "r4", "code_uid": "c3", "code": "Code 3"},
        {"row_type": "submission", "post_id": "r4", "code_uid": "c4", "code": "Code 4"},
        {"row_type": "submission", "post_id": "r4", "code_uid": "c5", "code": "Code 5"},
    ]

    metrics = compute_coverage_metrics(total_rows=5, entries=entries, codes=codes)
    assert metrics["total_rows"] == 5
    assert metrics["coded_rows"] == 4
    assert metrics["uncoded_rows"] == 1
    assert metrics["coded_percentage"] == 80.0
    assert metrics["uncoded_percentage"] == 20.0
    assert metrics["total_entries"] == 11
    assert metrics["distinct_codes_applied"] == 5

    dist = metrics["codes_per_row"]["distribution"]
    assert dist["0"] == 1
    assert dist["1"] == 1
    assert dist["2"] == 1
    assert dist["3+"] == 2

    # Density buckets:
    buckets = {b["bucket"]: b["row_count"] for b in metrics["density_buckets"]}
    assert buckets["0 codes"] == 1
    assert buckets["1 code"] == 1
    assert buckets["2 codes"] == 1
    assert buckets["3-4 codes"] == 1
    assert buckets["5+ codes"] == 1


def test_family_rollups_and_renamed_codes():
    codes = [
        {"code_uid": "c1", "name": "Current Name", "family_uid": "fam_core", "family_name": "Core Themes", "position": 1}
    ]
    # Entry has older code name "Old Name" but stable code_uid="c1"
    entries = [
        {"row_type": "submission", "post_id": "p1", "code_uid": "c1", "code": "Old Name"},
        {"row_type": "submission", "post_id": "p2", "code_uid": "c1", "code": "Old Name"},
    ]

    metrics = compute_coverage_metrics(total_rows=2, entries=entries, codes=codes)
    rollups = metrics["family_rollups"]
    assert len(rollups) == 1
    fam = rollups[0]
    assert fam["family_uid"] == "fam_core"
    assert fam["family_name"] == "Core Themes"
    assert fam["entry_count"] == 2
    assert fam["row_count"] == 2
    assert fam["row_percentage"] == 100.0

    # Code inside family resolves to current name "Current Name" via code_uid
    code_in_fam = fam["codes"][0]
    assert code_in_fam["code_uid"] == "c1"
    assert code_in_fam["name"] == "Current Name"
    assert code_in_fam["entry_count"] == 2
    assert code_in_fam["row_count"] == 2
