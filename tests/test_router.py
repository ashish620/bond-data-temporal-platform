"""
Tests for TemporalRouter routing logic.

Covers routing decisions, boundary conditions, and the `sources` field.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.config import CUTOFF_DATE
from app.models import BondSnapshot
from app.router import TemporalRouter


def make_snapshot(isin: str, snapshot_date: date, source: str) -> BondSnapshot:
    return BondSnapshot(
        isin=isin,
        snapshot_date=snapshot_date,
        issuer_name="Test Issuer",
        maturity_date=date(2030, 1, 1),
        coupon_rate=3.5,
        currency="USD",
        face_value=1000.0,
        source=source,
    )


@pytest.fixture
def mock_router():
    """TemporalRouter with mocked MongoDB collections."""
    with patch("app.router.motor.motor_asyncio.AsyncIOMotorClient"):
        router = TemporalRouter()
        router._legacy_col = MagicMock()
        router._current_col = MagicMock()
        yield router


# ---------------------------------------------------------------------------
# _determine_sources unit tests
# ---------------------------------------------------------------------------


def test_determine_sources_legacy_only(mock_router):
    """Dates entirely before cutoff → legacy only."""
    assert mock_router._determine_sources(date(2025, 1, 1), date(2025, 12, 31)) == "legacy"


def test_determine_sources_legacy_boundary(mock_router):
    """to_date exactly 2025-12-31 (one day before cutoff) → legacy only."""
    assert mock_router._determine_sources(date(2025, 1, 1), date(2025, 12, 31)) == "legacy"


def test_determine_sources_current_only(mock_router):
    """from_date exactly at cutoff → current only."""
    assert mock_router._determine_sources(CUTOFF_DATE, date(2026, 6, 30)) == "current"


def test_determine_sources_current_only_after_cutoff(mock_router):
    """Dates entirely after cutoff → current only."""
    assert mock_router._determine_sources(date(2026, 3, 1), date(2026, 12, 31)) == "current"


def test_determine_sources_both(mock_router):
    """Date range spanning cutoff → both DBs."""
    assert mock_router._determine_sources(date(2025, 6, 1), date(2026, 6, 1)) == "both"


def test_determine_sources_boundary_both(mock_router):
    """2025-12-31 to 2026-01-01 spans the cutoff → both DBs."""
    assert mock_router._determine_sources(date(2025, 12, 31), date(2026, 1, 1)) == "both"


# ---------------------------------------------------------------------------
# Full query() tests with mocked fetch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_routes_to_legacy_only(mock_router):
    """Query with to_date before cutoff should only hit legacy DB."""
    legacy_snap = make_snapshot("XS1234567890", date(2025, 6, 15), "legacy")

    with patch.object(
        mock_router,
        "_fetch_from_collection",
        new_callable=AsyncMock,
        return_value=[legacy_snap],
    ) as mock_fetch:
        snapshots, sources = await mock_router.query(
            "XS1234567890", date(2025, 1, 1), date(2025, 12, 31)
        )

    assert sources == "legacy"
    assert snapshots == [legacy_snap]
    # Should only be called once (for legacy)
    assert mock_fetch.call_count == 1
    # _fetch_from_collection args: (col, isin, from_date, to_date, source_label)
    assert mock_fetch.call_args[0][4] == "legacy"


@pytest.mark.asyncio
async def test_query_routes_to_current_only(mock_router):
    """Query with from_date at cutoff should only hit current DB."""
    current_snap = make_snapshot("XS1234567890", date(2026, 3, 1), "current")

    with patch.object(
        mock_router,
        "_fetch_from_collection",
        new_callable=AsyncMock,
        return_value=[current_snap],
    ) as mock_fetch:
        snapshots, sources = await mock_router.query(
            "XS1234567890", date(2026, 1, 1), date(2026, 6, 30)
        )

    assert sources == "current"
    assert snapshots == [current_snap]
    assert mock_fetch.call_count == 1
    # _fetch_from_collection args: (col, isin, from_date, to_date, source_label)
    assert mock_fetch.call_args[0][4] == "current"


@pytest.mark.asyncio
async def test_query_routes_to_both_dbs(mock_router):
    """Query spanning cutoff should hit both DBs in parallel and merge results."""
    legacy_snap = make_snapshot("XS1234567890", date(2025, 12, 15), "legacy")
    current_snap = make_snapshot("XS1234567890", date(2026, 1, 15), "current")

    call_results = {
        "legacy": [legacy_snap],
        "current": [current_snap],
    }

    async def side_effect(col, isin, from_date, to_date, source_label):
        return call_results[source_label]

    with patch.object(mock_router, "_fetch_from_collection", side_effect=side_effect):
        snapshots, sources = await mock_router.query(
            "XS1234567890", date(2025, 6, 1), date(2026, 6, 1)
        )

    assert sources == "both"
    assert len(snapshots) == 2
    assert snapshots[0].source == "legacy"
    assert snapshots[1].source == "current"


@pytest.mark.asyncio
async def test_query_results_sorted_by_snapshot_date(mock_router):
    """Merged results from both DBs must be sorted by snapshot_date ascending."""
    snap1 = make_snapshot("XS1234567890", date(2025, 12, 31), "legacy")
    snap2 = make_snapshot("XS1234567890", date(2026, 1, 1), "current")
    snap3 = make_snapshot("XS1234567890", date(2025, 6, 1), "legacy")

    async def side_effect(col, isin, from_date, to_date, source_label):
        if source_label == "legacy":
            return [snap1, snap3]
        return [snap2]

    with patch.object(mock_router, "_fetch_from_collection", side_effect=side_effect):
        snapshots, sources = await mock_router.query(
            "XS1234567890", date(2025, 1, 1), date(2026, 6, 1)
        )

    assert sources == "both"
    dates = [s.snapshot_date for s in snapshots]
    assert dates == sorted(dates)


@pytest.mark.asyncio
async def test_query_sources_field_legacy(mock_router):
    """sources field returns 'legacy' when query is legacy-only."""
    with patch.object(
        mock_router, "_fetch_from_collection", new_callable=AsyncMock, return_value=[]
    ):
        _, sources = await mock_router.query(
            "XS9999999999", date(2024, 1, 1), date(2025, 12, 31)
        )
    assert sources == "legacy"


@pytest.mark.asyncio
async def test_query_sources_field_current(mock_router):
    """sources field returns 'current' when query is current-only."""
    with patch.object(
        mock_router, "_fetch_from_collection", new_callable=AsyncMock, return_value=[]
    ):
        _, sources = await mock_router.query(
            "XS9999999999", date(2026, 1, 1), date(2026, 12, 31)
        )
    assert sources == "current"


@pytest.mark.asyncio
async def test_query_sources_field_both(mock_router):
    """sources field returns 'both' when query spans cutoff."""
    async def side_effect(col, isin, from_date, to_date, source_label):
        return []

    with patch.object(mock_router, "_fetch_from_collection", side_effect=side_effect):
        _, sources = await mock_router.query(
            "XS9999999999", date(2025, 12, 31), date(2026, 1, 1)
        )
    assert sources == "both"


# ---------------------------------------------------------------------------
# Boundary condition tests
# ---------------------------------------------------------------------------


def test_boundary_exactly_2025_12_31_is_legacy(mock_router):
    """Exactly 2025-12-31 as both from and to → legacy only."""
    assert mock_router._determine_sources(date(2025, 12, 31), date(2025, 12, 31)) == "legacy"


def test_boundary_exactly_2026_01_01_is_current(mock_router):
    """Exactly 2026-01-01 as from_date → current only."""
    assert mock_router._determine_sources(date(2026, 1, 1), date(2026, 1, 1)) == "current"


def test_boundary_2025_12_31_to_2026_01_01_is_both(mock_router):
    """2025-12-31 to 2026-01-01 straddles cutoff → both DBs."""
    assert mock_router._determine_sources(date(2025, 12, 31), date(2026, 1, 1)) == "both"


def test_cutoff_date_constant():
    """CUTOFF_DATE must be exactly 2026-01-01."""
    assert CUTOFF_DATE == date(2026, 1, 1)
