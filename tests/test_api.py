"""
API endpoint tests for Bond Data Intelligence Platform.

Tests cover pagination, cross-DB merging, boundary conditions, and
the stubbed NLP endpoint.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.bonds import get_temporal_router
from app.main import app
from app.models import BondSnapshot
from app.router import TemporalRouter


def make_snapshot(
    isin: str,
    snapshot_date: date,
    source: str,
    issuer_name: str = "Test Issuer",
) -> BondSnapshot:
    return BondSnapshot(
        isin=isin,
        snapshot_date=snapshot_date,
        issuer_name=issuer_name,
        maturity_date=date(2030, 1, 1),
        coupon_rate=3.5,
        currency="USD",
        face_value=1000.0,
        source=source,
    )


def _sorted_snapshots(snapshots: list[BondSnapshot]) -> list[BondSnapshot]:
    return sorted(snapshots, key=lambda s: s.snapshot_date)


def build_legacy_snapshots(isin: str, count: int = 5) -> list[BondSnapshot]:
    """Generate `count` legacy snapshots starting from 2025-01-01."""
    return [
        make_snapshot(isin, date(2025, 1 + i % 12, 1), "legacy")
        for i in range(count)
    ]


def build_current_snapshots(isin: str, count: int = 5) -> list[BondSnapshot]:
    """Generate `count` current snapshots starting from 2026-01-01."""
    return [
        make_snapshot(isin, date(2026, 1 + i % 12, 1), "current")
        for i in range(count)
    ]


@pytest.fixture
def client():
    """TestClient with a mocked TemporalRouter."""
    with TestClient(app) as c:
        yield c


def mock_router_returning(snapshots: list[BondSnapshot], sources: str):
    """Return a TemporalRouter dependency override that returns fixed data."""
    mock = MagicMock(spec=TemporalRouter)
    mock.query = AsyncMock(return_value=(_sorted_snapshots(snapshots), sources))
    return mock


# ---------------------------------------------------------------------------
# GET /api/v1/bonds — basic routing
# ---------------------------------------------------------------------------


def test_bonds_endpoint_legacy_only(client):
    """Query with to_date before cutoff should return sources='legacy'."""
    snapshots = build_legacy_snapshots("XS1234567890", 3)
    app.dependency_overrides[get_temporal_router] = lambda: mock_router_returning(
        snapshots, "legacy"
    )

    resp = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2025-01-01",
            "to_date": "2025-12-31",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sources"] == "legacy"
    assert body["total"] == 3
    app.dependency_overrides.clear()


def test_bonds_endpoint_current_only(client):
    """Query with from_date at cutoff should return sources='current'."""
    snapshots = build_current_snapshots("XS1234567890", 3)
    app.dependency_overrides[get_temporal_router] = lambda: mock_router_returning(
        snapshots, "current"
    )

    resp = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2026-01-01",
            "to_date": "2026-06-30",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sources"] == "current"
    assert body["total"] == 3
    app.dependency_overrides.clear()


def test_bonds_endpoint_both_sources(client):
    """Query spanning cutoff should return sources='both'."""
    all_snaps = build_legacy_snapshots("XS1234567890", 3) + build_current_snapshots(
        "XS1234567890", 3
    )
    app.dependency_overrides[get_temporal_router] = lambda: mock_router_returning(
        all_snaps, "both"
    )

    resp = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2025-01-01",
            "to_date": "2026-06-30",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sources"] == "both"
    assert body["total"] == 6
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Pagination tests
# ---------------------------------------------------------------------------


def test_pagination_page1_returns_first_n_records(client):
    """Page 1 should return first page_size records."""
    snapshots = build_legacy_snapshots("XS1234567890", 25)
    app.dependency_overrides[get_temporal_router] = lambda: mock_router_returning(
        snapshots, "legacy"
    )

    resp = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2025-01-01",
            "to_date": "2025-12-31",
            "page": 1,
            "page_size": 10,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 25
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert len(body["data"]) == 10
    app.dependency_overrides.clear()


def test_pagination_page2_returns_next_n_records(client):
    """Page 2 should return the next page_size records."""
    snapshots = build_legacy_snapshots("XS1234567890", 25)
    app.dependency_overrides[get_temporal_router] = lambda: mock_router_returning(
        snapshots, "legacy"
    )

    resp = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2025-01-01",
            "to_date": "2025-12-31",
            "page": 2,
            "page_size": 10,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 2
    assert len(body["data"]) == 10
    app.dependency_overrides.clear()


def test_pagination_last_page_returns_remaining_records(client):
    """Last page should return only the remaining records."""
    snapshots = build_legacy_snapshots("XS1234567890", 25)
    app.dependency_overrides[get_temporal_router] = lambda: mock_router_returning(
        snapshots, "legacy"
    )

    resp = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2025-01-01",
            "to_date": "2025-12-31",
            "page": 3,
            "page_size": 10,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 3
    assert len(body["data"]) == 5  # 25 total, pages of 10: last page has 5
    app.dependency_overrides.clear()


def test_pagination_empty_page_beyond_total_returns_empty_not_error(client):
    """Requesting a page beyond total results should return empty list, not an error."""
    snapshots = build_legacy_snapshots("XS1234567890", 5)
    app.dependency_overrides[get_temporal_router] = lambda: mock_router_returning(
        snapshots, "legacy"
    )

    resp = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2025-01-01",
            "to_date": "2025-12-31",
            "page": 99,
            "page_size": 20,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["total"] == 5  # total count is still accurate
    app.dependency_overrides.clear()


def test_pagination_total_count_is_accurate(client):
    """Total count in response should always reflect the true number of results."""
    snapshots = build_legacy_snapshots("XS1234567890", 42)
    app.dependency_overrides[get_temporal_router] = lambda: mock_router_returning(
        snapshots, "legacy"
    )

    resp = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2025-01-01",
            "to_date": "2025-12-31",
            "page": 1,
            "page_size": 20,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 42
    app.dependency_overrides.clear()


def test_pagination_cross_db_merged_result_set(client):
    """
    Cross-DB pagination: when results span both DBs, pagination should correctly
    handle the merged result set as a single ordered list.
    """
    legacy_snaps = build_legacy_snapshots("XS1234567890", 7)
    current_snaps = build_current_snapshots("XS1234567890", 15)
    all_snaps = legacy_snaps + current_snaps  # 22 total

    app.dependency_overrides[get_temporal_router] = lambda: mock_router_returning(
        all_snaps, "both"
    )

    # Page 1: records 1-10
    resp1 = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2025-01-01",
            "to_date": "2026-12-31",
            "page": 1,
            "page_size": 10,
        },
    )
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert body1["total"] == 22
    assert len(body1["data"]) == 10

    # Page 2: records 11-20
    resp2 = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2025-01-01",
            "to_date": "2026-12-31",
            "page": 2,
            "page_size": 10,
        },
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert len(body2["data"]) == 10

    # Page 3: records 21-22
    resp3 = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2025-01-01",
            "to_date": "2026-12-31",
            "page": 3,
            "page_size": 10,
        },
    )
    assert resp3.status_code == 200
    body3 = resp3.json()
    assert len(body3["data"]) == 2

    # No duplicates across pages
    all_isins = (
        [r["snapshot_date"] for r in body1["data"]]
        + [r["snapshot_date"] for r in body2["data"]]
        + [r["snapshot_date"] for r in body3["data"]]
    )
    assert len(all_isins) == 22

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Boundary condition tests
# ---------------------------------------------------------------------------


def test_boundary_2025_12_31_legacy_only(client):
    """Exactly 2025-12-31 as to_date → legacy only."""
    snapshots = build_legacy_snapshots("XS1234567890", 2)
    app.dependency_overrides[get_temporal_router] = lambda: mock_router_returning(
        snapshots, "legacy"
    )

    resp = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2025-01-01",
            "to_date": "2025-12-31",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["sources"] == "legacy"
    app.dependency_overrides.clear()


def test_boundary_2026_01_01_current_only(client):
    """Exactly 2026-01-01 as from_date → current only."""
    snapshots = build_current_snapshots("XS1234567890", 2)
    app.dependency_overrides[get_temporal_router] = lambda: mock_router_returning(
        snapshots, "current"
    )

    resp = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2026-01-01",
            "to_date": "2026-06-30",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["sources"] == "current"
    app.dependency_overrides.clear()


def test_boundary_2025_12_31_to_2026_01_01_both(client):
    """Range 2025-12-31 to 2026-01-01 → both DBs."""
    snaps = [
        make_snapshot("XS1234567890", date(2025, 12, 31), "legacy"),
        make_snapshot("XS1234567890", date(2026, 1, 1), "current"),
    ]
    app.dependency_overrides[get_temporal_router] = lambda: mock_router_returning(
        snaps, "both"
    )

    resp = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2025-12-31",
            "to_date": "2026-01-01",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["sources"] == "both"
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


def test_invalid_date_range_returns_400(client):
    """from_date after to_date should return 400."""
    snapshots: list[BondSnapshot] = []
    app.dependency_overrides[get_temporal_router] = lambda: mock_router_returning(
        snapshots, "legacy"
    )

    resp = client.get(
        "/api/v1/bonds",
        params={
            "isin": "XS1234567890",
            "from_date": "2026-01-01",
            "to_date": "2025-01-01",
        },
    )
    assert resp.status_code == 400
    app.dependency_overrides.clear()


def test_missing_required_params_returns_422(client):
    """Missing required query params should return 422 Unprocessable Entity."""
    resp = client.get("/api/v1/bonds", params={"isin": "XS1234567890"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/query — stubbed NLP endpoint
# ---------------------------------------------------------------------------


def test_nlp_query_returns_501(client):
    """POST /api/v1/query should return 200 with not_implemented status."""
    resp = client.post("/api/v1/query")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "not_implemented"
    assert "Day 2" in body["message"]
