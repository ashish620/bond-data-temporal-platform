"""
Day 4 — Agent tool functions.

Four async tools called by the ReconciliationAgent during its Execute and
Validate phases:

  1. fetch_from_legacy_db      — historical snapshots from Legacy MongoDB
  2. fetch_from_current_db     — recent snapshots from Current MongoDB
  3. query_prospectus           — RAG-grounded prospectus lookup
  4. assess_field_consistency   — LLM-powered consistency assessment
"""

import logging
from datetime import date, timedelta
from typing import Any

from openai import AsyncOpenAI

from app.config import CUTOFF_DATE
from app.router import TemporalRouter
from day3.rag.query_engine import RAGQueryEngine

logger = logging.getLogger(__name__)


async def fetch_from_legacy_db(isin: str, router: TemporalRouter) -> list[dict]:
    """
    Fetch all legacy snapshots for *isin* covering the full legacy period
    (2020-01-01 → CUTOFF_DATE - 1 day).

    Returns:
        List of snapshot dicts (empty if none found).
    """
    from_date = date(2020, 1, 1)
    to_date = CUTOFF_DATE - timedelta(days=1)

    try:
        snapshots, _ = await router.query(isin, from_date, to_date)
        return [s.model_dump() for s in snapshots]
    except Exception:  # noqa: BLE001
        logger.exception("fetch_from_legacy_db failed for ISIN %s", isin)
        return []


async def fetch_from_current_db(isin: str, router: TemporalRouter) -> list[dict]:
    """
    Fetch all current snapshots for *isin* (CUTOFF_DATE → today).

    Returns:
        List of snapshot dicts (empty if none found).
    """
    from_date = CUTOFF_DATE
    to_date = date.today()

    try:
        snapshots, _ = await router.query(isin, from_date, to_date)
        return [s.model_dump() for s in snapshots]
    except Exception:  # noqa: BLE001
        logger.exception("fetch_from_current_db failed for ISIN %s", isin)
        return []


async def query_prospectus(isin: str, field: str, rag_engine: RAGQueryEngine) -> dict:
    """
    Query the prospectus for the authoritative value of a specific field.

    Builds a natural language question, calls the RAG engine, and normalises
    the result into a consistent dict.  If no prospectus has been ingested for
    the ISIN, returns a low-confidence "Not found" response instead of raising.

    Returns::

        {
            "answer":     str,
            "confidence": "high" | "medium" | "low",
            "sources":    list[dict],
        }
    """
    question = f"What is the {field} for bond {isin}?"
    try:
        result = await rag_engine.query(question, isin)
        return {
            "answer": result.answer,
            "confidence": result.confidence,
            "sources": [s.model_dump() for s in result.sources],
        }
    except ValueError:
        # No prospectus ingested for this ISIN — graceful degradation
        logger.info("No prospectus found for ISIN %s — field %s marked as low confidence", isin, field)
        return {
            "answer": "Not found in prospectus",
            "confidence": "low",
            "sources": [],
        }
    except Exception:  # noqa: BLE001
        logger.exception("query_prospectus failed for ISIN %s / field %s", isin, field)
        return {
            "answer": "Not found in prospectus",
            "confidence": "low",
            "sources": [],
        }


async def assess_field_consistency(
    field: str,
    incoming_value: Any,
    master_value: Any,
    legacy_values: list[Any],
    prospectus_answer: str,
    client: AsyncOpenAI,
) -> dict:
    """
    Use GPT-4o-mini to assess which value is most likely correct for the field.

    The LLM is given all four data points:
    - incoming value (from the uploaded file)
    - master value (current security master)
    - historical legacy values
    - prospectus answer

    Returns::

        {
            "recommended_action": "ACCEPT_INCOMING" | "KEEP_MASTER" | "MANUAL_REVIEW",
            "reasoning":          str,
            "prospectus_value":   str | None,
        }
    """
    system_prompt = (
        "You are a bond data reconciliation specialist. "
        "Assess which field value is most authoritative and return a JSON object with exactly "
        "three keys: recommended_action (one of ACCEPT_INCOMING, KEEP_MASTER, MANUAL_REVIEW), "
        "reasoning (concise explanation, max 2 sentences), and prospectus_value (the value "
        "extracted from the prospectus answer, or null if not found). "
        "Return ONLY valid JSON — no markdown, no extra text."
    )

    user_prompt = (
        f"Field: {field}\n"
        f"Incoming value (from uploaded file): {incoming_value}\n"
        f"Master value (current security master): {master_value}\n"
        f"Historical legacy values: {legacy_values if legacy_values else 'none available'}\n"
        f"Prospectus answer: {prospectus_answer}\n\n"
        "Which value should be used? Return JSON only."
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        import json

        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)
        return {
            "recommended_action": result.get("recommended_action", "MANUAL_REVIEW"),
            "reasoning": result.get("reasoning", "Unable to determine — manual review required."),
            "prospectus_value": result.get("prospectus_value"),
        }
    except Exception:  # noqa: BLE001
        logger.exception("assess_field_consistency failed for field %s", field)
        return {
            "recommended_action": "MANUAL_REVIEW",
            "reasoning": "Assessment failed — manual review required.",
            "prospectus_value": None,
        }
