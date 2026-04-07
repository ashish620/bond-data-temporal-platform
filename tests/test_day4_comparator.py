"""
Tests for Day 4 — Comparator field-level diff engine.

Covers:
- Matching records (no mismatches expected)
- Records with differences (issuer_name, coupon_rate, currency)
- Float tolerance edge cases (values within / outside 0.0001)
"""

from datetime import date

import pytest

from app.models import BondSnapshot
from day4.models import IncomingRecord
from day4.pipeline.comparator import COMPARABLE_FIELDS, Comparator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_incoming(**overrides) -> IncomingRecord:
    """Return an IncomingRecord with sensible defaults, applying any overrides."""
    defaults = dict(
        isin="XS1234567890",
        snapshot_date=date(2026, 3, 1),
        issuer_name="ACME Corp",
        maturity_date=date(2030, 6, 15),
        coupon_rate=4.5,
        currency="USD",
        face_value=1_000_000.0,
    )
    defaults.update(overrides)
    return IncomingRecord(**defaults)


def _make_master(**overrides) -> BondSnapshot:
    """Return a BondSnapshot (security master) with sensible defaults."""
    defaults = dict(
        isin="XS1234567890",
        snapshot_date=date(2026, 3, 1),
        issuer_name="ACME Corp",
        maturity_date=date(2030, 6, 15),
        coupon_rate=4.5,
        currency="USD",
        face_value=1_000_000.0,
        source="current",
    )
    defaults.update(overrides)
    return BondSnapshot(**defaults)


@pytest.fixture
def comparator() -> Comparator:
    return Comparator()


# ---------------------------------------------------------------------------
# No-mismatch cases
# ---------------------------------------------------------------------------


def test_compare_identical_records_no_mismatches(comparator):
    """Identical incoming and master records should produce zero mismatches."""
    incoming = _make_incoming()
    master = _make_master()
    mismatches = comparator.compare(incoming, master)
    assert mismatches == []


def test_compare_case_insensitive_issuer_name(comparator):
    """issuer_name comparison should be case-insensitive."""
    incoming = _make_incoming(issuer_name="acme corp")
    master = _make_master(issuer_name="ACME CORP")
    mismatches = comparator.compare(incoming, master)
    # Different case — should NOT be flagged as a mismatch
    assert all(m.field != "issuer_name" for m in mismatches)


def test_compare_strips_whitespace_in_strings(comparator):
    """Leading/trailing whitespace in string fields should be ignored."""
    incoming = _make_incoming(currency="  USD  ")
    master = _make_master(currency="USD")
    mismatches = comparator.compare(incoming, master)
    assert all(m.field != "currency" for m in mismatches)


def test_compare_float_within_tolerance_no_mismatch(comparator):
    """coupon_rate difference of exactly 0.0001 should NOT be flagged."""
    incoming = _make_incoming(coupon_rate=4.5001)
    master = _make_master(coupon_rate=4.5)
    mismatches = comparator.compare(incoming, master)
    assert all(m.field != "coupon_rate" for m in mismatches)


def test_compare_float_at_zero_tolerance_boundary(comparator):
    """coupon_rate values exactly equal → no mismatch."""
    incoming = _make_incoming(coupon_rate=4.5)
    master = _make_master(coupon_rate=4.5)
    mismatches = comparator.compare(incoming, master)
    assert mismatches == []


# ---------------------------------------------------------------------------
# Mismatch detection cases
# ---------------------------------------------------------------------------


def test_compare_issuer_name_mismatch(comparator):
    """Different issuer_name values should produce exactly one FieldMismatch."""
    incoming = _make_incoming(issuer_name="Beta Ltd")
    master = _make_master(issuer_name="ACME Corp")
    mismatches = comparator.compare(incoming, master)

    assert len(mismatches) == 1
    mm = mismatches[0]
    assert mm.field == "issuer_name"
    assert mm.incoming_value == "Beta Ltd"
    assert mm.master_value == "ACME Corp"


def test_compare_coupon_rate_mismatch(comparator):
    """coupon_rate difference beyond tolerance should produce a FieldMismatch."""
    incoming = _make_incoming(coupon_rate=5.0)
    master = _make_master(coupon_rate=4.5)
    mismatches = comparator.compare(incoming, master)

    assert len(mismatches) == 1
    mm = mismatches[0]
    assert mm.field == "coupon_rate"
    assert mm.incoming_value == 5.0
    assert mm.master_value == 4.5


def test_compare_currency_mismatch(comparator):
    """Different currency values should produce a FieldMismatch."""
    incoming = _make_incoming(currency="EUR")
    master = _make_master(currency="USD")
    mismatches = comparator.compare(incoming, master)

    assert len(mismatches) == 1
    mm = mismatches[0]
    assert mm.field == "currency"
    assert mm.incoming_value == "EUR"
    assert mm.master_value == "USD"


def test_compare_multiple_mismatches(comparator):
    """Multiple differing fields should each produce a separate FieldMismatch."""
    incoming = _make_incoming(issuer_name="Beta Ltd", coupon_rate=6.0, currency="GBP")
    master = _make_master()
    mismatches = comparator.compare(incoming, master)

    mismatch_fields = {m.field for m in mismatches}
    assert "issuer_name" in mismatch_fields
    assert "coupon_rate" in mismatch_fields
    assert "currency" in mismatch_fields
    assert len(mismatches) == 3


def test_compare_maturity_date_mismatch(comparator):
    """Different maturity_date values should produce a FieldMismatch."""
    incoming = _make_incoming(maturity_date=date(2035, 1, 1))
    master = _make_master(maturity_date=date(2030, 6, 15))
    mismatches = comparator.compare(incoming, master)

    assert len(mismatches) == 1
    mm = mismatches[0]
    assert mm.field == "maturity_date"


def test_compare_face_value_mismatch(comparator):
    """face_value difference beyond tolerance should produce a FieldMismatch."""
    incoming = _make_incoming(face_value=500_000.0)
    master = _make_master(face_value=1_000_000.0)
    mismatches = comparator.compare(incoming, master)

    assert any(m.field == "face_value" for m in mismatches)


# ---------------------------------------------------------------------------
# Float tolerance edge cases
# ---------------------------------------------------------------------------


def test_float_tolerance_just_below_boundary_no_mismatch(comparator):
    """Difference of 0.00009 (< 0.0001) should NOT be flagged."""
    incoming = _make_incoming(coupon_rate=4.50009)
    master = _make_master(coupon_rate=4.5)
    mismatches = comparator.compare(incoming, master)
    assert all(m.field != "coupon_rate" for m in mismatches)


def test_float_tolerance_just_above_boundary_flagged(comparator):
    """Difference of 0.00015 (> 0.0001) SHOULD be flagged."""
    incoming = _make_incoming(coupon_rate=4.50015)
    master = _make_master(coupon_rate=4.5)
    mismatches = comparator.compare(incoming, master)
    assert any(m.field == "coupon_rate" for m in mismatches)


# ---------------------------------------------------------------------------
# COMPARABLE_FIELDS contract
# ---------------------------------------------------------------------------


def test_comparable_fields_includes_required_fields():
    """COMPARABLE_FIELDS must include all five expected business fields."""
    required = {"issuer_name", "maturity_date", "coupon_rate", "currency", "face_value"}
    assert required.issubset(set(COMPARABLE_FIELDS))


def test_compare_isin_not_compared(comparator):
    """isin is not in COMPARABLE_FIELDS — different ISINs should NOT produce mismatches."""
    incoming = _make_incoming(isin="XS9999999999")
    master = _make_master(isin="XS1234567890")
    # Even though ISINs differ, the comparator should not flag it
    mismatches = comparator.compare(incoming, master)
    assert all(m.field != "isin" for m in mismatches)
