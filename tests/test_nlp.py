"""
Tests for the NLP query interface — extractor model validation and endpoint behaviour.

All external calls (OpenAI + MongoDB) are mocked — no real API calls are made.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.bonds import get_temporal_router
from app.main import app
from app.models import BondSnapshot, NLPQueryResponse
from app.nlp.extractor import ExtractedQueryParams, NLPExtractor
from app.router import TemporalRouter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_snapshot(
    isin: str = "XS1234567890",
    snapshot_date: date = date(2025, 3, 1),
    source: str = "legacy",
) -> BondSnapshot:
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
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# ExtractedQueryParams model validation
# ---------------------------------------------------------------------------


def test_extracted_query_params_valid():
    """ExtractedQueryParams should accept valid isin and date fields."""
    params = ExtractedQueryParams(
        isin="XS1234567890",
        from_date=date(2025, 1, 1),
        to_date=date(2025, 3, 31),
    )
    assert params.isin == "XS1234567890"
    assert params.from_date == date(2025, 1, 1)
    assert params.to_date == date(2025, 3, 31)


def test_extracted_query_params_accepts_string_dates():
    """ExtractedQueryParams should coerce string dates to date objects."""
    params = ExtractedQueryParams(
        isin="XS1234567890",
        from_date="2025-01-01",  # type: ignore[arg-type]
        to_date="2025-03-31",  # type: ignore[arg-type]
    )
    assert params.from_date == date(2025, 1, 1)
    assert params.to_date == date(2025, 3, 31)


def test_extracted_query_params_rejects_missing_isin():
    """ExtractedQueryParams should raise ValidationError when isin is missing."""
    with pytest.raises(ValidationError):
        ExtractedQueryParams(
            from_date=date(2025, 1, 1),
            to_date=date(2025, 3, 31),
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# POST /api/v1/query — 503 when OPENAI_API_KEY is not set
# ---------------------------------------------------------------------------


def test_nlp_query_returns_503_when_api_key_missing(client):
    """Endpoint should return 503 when OPENAI_API_KEY env var is not set."""
    with patch.dict("os.environ", {}, clear=True):
        # Ensure OPENAI_API_KEY is absent
        import os

        os.environ.pop("OPENAI_API_KEY", None)

        resp = client.post("/api/v1/query", json={"query": "Show me XS1234567890 Q1 2025"})

    assert resp.status_code == 503
    assert "OPENAI_API_KEY" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /api/v1/query — 422 when extraction fails
# ---------------------------------------------------------------------------


def test_nlp_query_returns_422_when_extraction_fails(client):
    """Endpoint should return 422 when NLPExtractor.extract raises ValueError."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        mock_extractor = MagicMock(spec=NLPExtractor)
        mock_extractor.extract = AsyncMock(
            side_effect=ValueError("No valid ISIN found in query")
        )

        with patch("app.api.bonds.NLPExtractor", return_value=mock_extractor):
            resp = client.post(
                "/api/v1/query",
                json={"query": "tell me about the weather"},
            )

    assert resp.status_code == 422
    assert "No valid ISIN found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /api/v1/query — 200 with correct NLPQueryResponse structure
# ---------------------------------------------------------------------------


def test_nlp_query_returns_correct_response_structure(client):
    """Endpoint should return NLPQueryResponse with extracted params and bond data."""
    snapshots = [make_snapshot("XS1234567890", date(2025, 1, 1), "legacy")]

    extracted = ExtractedQueryParams(
        isin="XS1234567890",
        from_date=date(2025, 1, 1),
        to_date=date(2025, 3, 31),
    )

    mock_router = MagicMock(spec=TemporalRouter)
    mock_router.query = AsyncMock(return_value=(snapshots, "legacy"))

    mock_extractor = MagicMock(spec=NLPExtractor)
    mock_extractor.extract = AsyncMock(return_value=extracted)

    app.dependency_overrides[get_temporal_router] = lambda: mock_router

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        with patch("app.api.bonds.NLPExtractor", return_value=mock_extractor):
            resp = client.post(
                "/api/v1/query",
                json={"query": "Show me XS1234567890 bonds from Q1 2025"},
            )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()

    assert body["natural_query"] == "Show me XS1234567890 bonds from Q1 2025"
    assert body["extracted_isin"] == "XS1234567890"
    assert body["extracted_from_date"] == "2025-01-01"
    assert body["extracted_to_date"] == "2025-03-31"
    assert body["sources"] == "legacy"
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert len(body["data"]) == 1
    assert body["data"][0]["isin"] == "XS1234567890"


def test_nlp_query_pagination_fields(client):
    """Endpoint should respect page and page_size from request body."""
    snapshots = [make_snapshot("XS9876543210", date(2026, 1, i + 1), "current") for i in range(5)]

    extracted = ExtractedQueryParams(
        isin="XS9876543210",
        from_date=date(2026, 1, 1),
        to_date=date(2026, 1, 31),
    )

    mock_router = MagicMock(spec=TemporalRouter)
    mock_router.query = AsyncMock(return_value=(snapshots, "current"))

    mock_extractor = MagicMock(spec=NLPExtractor)
    mock_extractor.extract = AsyncMock(return_value=extracted)

    app.dependency_overrides[get_temporal_router] = lambda: mock_router

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        with patch("app.api.bonds.NLPExtractor", return_value=mock_extractor):
            resp = client.post(
                "/api/v1/query",
                json={"query": "XS9876543210 January 2026", "page": 2, "page_size": 2},
            )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert body["total"] == 5
    assert len(body["data"]) == 2  # page 2 of 5, page_size 2 → items 3 & 4
