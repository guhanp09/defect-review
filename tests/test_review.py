from copy import deepcopy
from datetime import date

import pytest

from defect_review.reliability import poisson_rate, rate_review
from defect_review.review import normalize, records, warehouse

CATALOG = {
    "2910": {"title": "HYDRAULIC SYSTEM, MAIN", "ata_chapter": "29"},
    "3418": {"title": "STALL WARNING SYSTEM", "ata_chapter": None},
}


def report(identity="A", occurrence="01/01/2025", **changes):
    row = dict(
        report_id=identity,
        occurrence_date=occurrence,
        submitted_at="2025-02-01T12:00:00-05:00",
        make="EXAMPLE",
        model="T1",
        jasc="2910",
        part_name="PUMP",
        part_number="P1",
        part_condition="LEAK",
        component_name="",
        aircraft_key="synthetic-test-aircraft",
    )
    return {**row, **changes}


def test_cutoff_precedes_identity_conflict_detection():
    rows = [report(), report(submitted_at="2026-01-01T00:00:00-05:00", part_number="NEW")]
    accepted, quality = normalize(rows, CATALOG, date(2025, 12, 31))
    assert [r["part_number"] for r in accepted] == ["P1"]
    assert quality["after_cutoff"] == 1


def test_exact_duplicates_collapse_conflicts_quarantine_all_versions():
    rows = [report(), report(), report("B"), report("B", part_number="P2")]
    accepted, quality = normalize(rows, CATALOG, date(2026, 1, 1))
    assert [r["report_id"] for r in accepted] == ["A"]
    assert quality["exact_duplicate_rows"] == 1
    assert quality["conflicting_identity_rows"] == 2


@pytest.mark.parametrize(
    "changes,key",
    [
        ({"occurrence_date": "02/30/2025"}, "invalid_date"),
        ({"submitted_at": "2025-02-01T12:00:00"}, "invalid_date"),
        ({"occurrence_date": "03/01/2025"}, "occurrence_after_submission"),
        ({"report_id": ""}, "missing_identity"),
    ],
)
def test_bad_evidence_is_not_silently_fixed(changes, key):
    accepted, quality = normalize([report(**changes)], CATALOG, date(2026, 1, 1))
    assert accepted == []
    assert quality[key] == 1


def test_submission_cutoff_uses_utc_day():
    accepted, quality = normalize(
        [report(submitted_at="2025-02-01T23:30:00-05:00")], CATALOG, date(2025, 2, 1)
    )
    assert accepted == []
    assert quality["after_cutoff"] == 1


def test_unknown_and_jasc_stall_warning_do_not_become_ata34():
    rows, quality = normalize(
        [report(jasc="3418"), report("B", jasc="9999")], CATALOG, date(2026, 1, 1)
    )
    assert all(not r["ata_chapter"] for r in rows)
    assert quality["ata_grouping_requires_review"] == 2
    assert quality["unrecognized_jasc"] == 1


def test_sql_count_grain_and_30_day_candidate_boundaries():
    raw = [
        report("A"),
        report("B", "01/31/2025"),
        report("C", "01/31/2025"),
        report("D", "03/03/2025", submitted_at="2025-04-01T00:00:00Z"),
        report("E", aircraft_key=""),
        report("F", jasc="3418"),
    ]
    accepted, _ = normalize(raw, CATALOG, date(2026, 1, 1))
    connection = warehouse(accepted)
    pairs = records(connection, "SELECT * FROM repeat_candidates")
    assert [(p["prior_report_id"], p["report_id"], p["gap_days"]) for p in pairs] == [
        ("A", "B", 30),
        ("B", "C", 0),
    ]
    monthly = records(connection, "SELECT * FROM monthly_reports")
    assert sum(r["reports"] for r in monthly) == 6
    assert sum(r["reports"] for r in records(connection, "SELECT * FROM system_drilldown")) == 6
    assert monthly[0]["linked_aircraft"] == 1


def test_garwood_zero_events_retains_nonzero_upper_bound():
    result = poisson_rate(0, 1000)
    assert result["rate"] == result["lower"] == 0
    assert result["upper"] == pytest.approx(3.688879454, abs=1e-8)


@pytest.mark.parametrize(
    "events,exposure", [(1, 0), (-1, 100), (1.5, 100), (True, 100), (1, -1), (1, float("nan"))]
)
def test_invalid_rate_inputs_rejected(events, exposure):
    with pytest.raises(ValueError):
        poisson_rate(events, exposure)


def test_absent_or_zero_exposure_is_not_zero_rate():
    assert poisson_rate(2, None)["rate"] is None
    assert poisson_rate(0, 0)["upper"] is None


def test_later_counts_cannot_change_frozen_baseline_and_missing_hours_block_screen():
    rows = [
        {"month": "2025-01", "removals": 1, "flight_hours": 1000},
        {"month": "2025-02", "removals": 20, "flight_hours": 1000},
        {"month": "2025-03", "removals": 2, "flight_hours": None},
    ]
    original = rate_review(rows, baseline_months=1)
    changed = deepcopy(rows)
    changed[1]["removals"] = 100
    assert rate_review(changed, baseline_months=1)[1]["baseline_per_1000h"] == 1
    assert original[1]["screen"] == "investigate"
    assert original[2]["screen"] == "insufficient exposure"
    assert original[2]["mtbur_hours"] is None


def test_duplicate_month_rejected_instead_of_double_counting():
    rows = [{"month": "2025-01", "removals": 1, "flight_hours": 1000}] * 2
    with pytest.raises(ValueError, match="duplicate month"):
        rate_review(rows, baseline_months=1)


def test_missing_month_is_not_interpreted_as_zero_events():
    rows = [
        {"month": "2025-01", "removals": 1, "flight_hours": 1000},
        {"month": "2025-03", "removals": 1, "flight_hours": 1000},
    ]
    with pytest.raises(ValueError, match="missing month"):
        rate_review(rows, baseline_months=1)


def test_quarantine_is_traceable_to_source_identity():
    audit = []
    normalize([report("BAD-DATE", occurrence="03/01/2025")], CATALOG, date(2026, 1, 1), audit=audit)
    assert audit[0]["report_id"] == "BAD-DATE"
    assert audit[0]["reason"] == "occurrence_after_submission"
