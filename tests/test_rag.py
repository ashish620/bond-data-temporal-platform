"""
Tests for the Day 3 RAG validation endpoint.

All external calls (OpenAI + ChromaDB) are mocked — no real API calls made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from day3.api.validate import ValidationRequest, ValidationResponse
from day3.rag.query_engine import RAGQueryEngine, RAGQueryResult, RAGSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rag_result(answer: str = "The call schedule is par + 0.5% from 15 Jan 2027.") -> RAGQueryResult:
    return RAGQueryResult(
        answer=answer,
        sources=[
            RAGSource(page=3, document="XS1234567890_prospectus.pdf", excerpt="call at par + 0.5%")
        ],
        confidence="high",
    )


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# ValidationRequest model validation
# ---------------------------------------------------------------------------


def test_validation_request_valid():
    """ValidationRequest should accept a question with optional fields."""
    req = ValidationRequest(
        question="What is the call schedule?",
        field="call_schedule",
        security_master_value="par flat",
    )
    assert req.question == "What is the call schedule?"
    assert req.field == "call_schedule"
    assert req.security_master_value == "par flat"


def test_validation_request_question_only():
    """ValidationRequest should accept a question with no optional fields."""
    req = ValidationRequest(question="What is the coupon rate?")
    assert req.field is None
    assert req.security_master_value is None


def test_validation_request_rejects_missing_question():
    """ValidationRequest should raise ValidationError when question is missing."""
    with pytest.raises(ValidationError):
        ValidationRequest()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# POST /api/v3/validate/{isin} — 503 when OPENAI_API_KEY missing
# ---------------------------------------------------------------------------


def test_validate_returns_503_when_api_key_missing(client):
    """Endpoint should return 503 when OPENAI_API_KEY env var is not set."""
    with patch.dict("os.environ", {}, clear=True):
        import os

        os.environ.pop("OPENAI_API_KEY", None)

        resp = client.post(
            "/api/v3/validate/XS1234567890",
            json={"question": "What is the call schedule?"},
        )

    assert resp.status_code == 503
    assert "OPENAI_API_KEY" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /api/v3/validate/{isin} — 404 when no documents exist
# ---------------------------------------------------------------------------


def test_validate_returns_404_when_no_documents(client):
    """Endpoint should return 404 when no prospectus has been ingested for ISIN."""
    mock_engine = MagicMock(spec=RAGQueryEngine)
    mock_engine.query = AsyncMock(
        side_effect=ValueError("No documents found for ISIN XS9999999999. Please ingest prospectus first.")
    )

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        with patch("day3.api.validate.RAGQueryEngine", return_value=mock_engine):
            resp = client.post(
                "/api/v3/validate/XS9999999999",
                json={"question": "What is the call schedule?"},
            )

    assert resp.status_code == 404
    assert "No prospectus found" in resp.json()["detail"]
    assert "XS9999999999" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /api/v3/validate/{isin} — mismatch_detected: true
# ---------------------------------------------------------------------------


def test_validate_returns_mismatch_true(client):
    """
    Endpoint should return mismatch_detected=true and a recommendation when
    the security_master_value differs from the prospectus answer.
    """
    mock_engine = MagicMock(spec=RAGQueryEngine)
    mock_engine.query = AsyncMock(return_value=_make_rag_result())

    # Mock GPT comparison call to indicate a mismatch
    compare_mock = MagicMock()
    compare_mock.choices = [
        MagicMock(
            message=MagicMock(
                content='{"mismatch": true, "prospectus_value": "par + 0.5% call premium from 15 January 2027"}'
            )
        )
    ]

    async def mock_create(**kwargs):
        return compare_mock

    mock_openai_client = AsyncMock()
    mock_openai_client.chat.completions.create = mock_create

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        with patch("day3.api.validate.RAGQueryEngine", return_value=mock_engine):
            with patch("day3.api.validate.AsyncOpenAI", return_value=mock_openai_client):
                resp = client.post(
                    "/api/v3/validate/XS1234567890",
                    json={
                        "question": "What is the call schedule?",
                        "field": "call_schedule",
                        "security_master_value": "par flat",
                    },
                )

    assert resp.status_code == 200
    body = resp.json()
    assert body["isin"] == "XS1234567890"
    assert body["mismatch_detected"] is True
    assert body["security_master_value"] == "par flat"
    assert body["prospectus_value"] == "par + 0.5% call premium from 15 January 2027"
    assert body["recommendation"] == "Review call_schedule field in security master for ISIN XS1234567890"
    assert body["confidence"] == "high"
    assert len(body["sources"]) == 1
    assert body["sources"][0]["page"] == 3


# ---------------------------------------------------------------------------
# POST /api/v3/validate/{isin} — mismatch_detected: false
# ---------------------------------------------------------------------------


def test_validate_returns_mismatch_false(client):
    """
    Endpoint should return mismatch_detected=false when the security_master_value
    matches the prospectus answer.
    """
    mock_engine = MagicMock(spec=RAGQueryEngine)
    mock_engine.query = AsyncMock(
        return_value=RAGQueryResult(
            answer="The coupon rate is 4.500% per annum.",
            sources=[
                RAGSource(page=2, document="XS1234567890_prospectus.pdf", excerpt="4.500% per annum")
            ],
            confidence="high",
        )
    )

    compare_mock = MagicMock()
    compare_mock.choices = [
        MagicMock(
            message=MagicMock(
                content='{"mismatch": false, "prospectus_value": "4.500%"}'
            )
        )
    ]

    async def mock_create(**kwargs):
        return compare_mock

    mock_openai_client = AsyncMock()
    mock_openai_client.chat.completions.create = mock_create

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        with patch("day3.api.validate.RAGQueryEngine", return_value=mock_engine):
            with patch("day3.api.validate.AsyncOpenAI", return_value=mock_openai_client):
                resp = client.post(
                    "/api/v3/validate/XS1234567890",
                    json={
                        "question": "What is the coupon rate?",
                        "field": "coupon_rate",
                        "security_master_value": "4.500%",
                    },
                )

    assert resp.status_code == 200
    body = resp.json()
    assert body["mismatch_detected"] is False
    assert body["recommendation"] is None


# ---------------------------------------------------------------------------
# POST /api/v3/validate/{isin} — no security_master_value provided
# ---------------------------------------------------------------------------


def test_validate_without_security_master_value(client):
    """
    Endpoint should return a valid response with mismatch_detected=false when
    no security_master_value is supplied (question-only mode).
    """
    mock_engine = MagicMock(spec=RAGQueryEngine)
    mock_engine.query = AsyncMock(return_value=_make_rag_result())

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        with patch("day3.api.validate.RAGQueryEngine", return_value=mock_engine):
            resp = client.post(
                "/api/v3/validate/XS1234567890",
                json={"question": "What is the call schedule?"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["mismatch_detected"] is False
    assert body["security_master_value"] is None
    assert body["prospectus_value"] is None
    assert body["recommendation"] is None
    assert body["answer"] != ""
