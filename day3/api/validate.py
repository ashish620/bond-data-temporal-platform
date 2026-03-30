"""
Day 3 — Validation API Endpoint

POST /api/v3/validate/{isin}

Answers a natural language question grounded in the bond prospectus for the
given ISIN, optionally comparing the answer against a security master value
to detect data mismatches.
"""

import json
import os

from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel

from day3.rag.query_engine import RAGQueryEngine, RAGSource

router = APIRouter()


class ValidationRequest(BaseModel):
    """Request body for the validate endpoint."""

    question: str
    field: str | None = None
    security_master_value: str | None = None


class ValidationResponse(BaseModel):
    """Response model for the validate endpoint."""

    isin: str
    question: str
    answer: str
    sources: list[RAGSource]
    mismatch_detected: bool
    security_master_value: str | None
    prospectus_value: str | None
    recommendation: str | None
    confidence: str


@router.post("/validate/{isin}", response_model=ValidationResponse)
async def validate(isin: str, request: ValidationRequest) -> ValidationResponse:
    """
    Validate a security master field value against the bond prospectus.

    Returns a grounded answer from the prospectus, and if a
    security_master_value is supplied, flags any mismatch automatically.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured")

    engine = RAGQueryEngine()
    try:
        result = await engine.query(request.question, isin)
    except ValueError as exc:
        msg = str(exc)
        if "No documents found" in msg:
            raise HTTPException(
                status_code=404,
                detail=f"No prospectus found for ISIN {isin}. Please ingest documents first.",
            ) from exc
        raise HTTPException(status_code=500, detail=msg) from exc

    mismatch_detected = False
    prospectus_value: str | None = None
    recommendation: str | None = None

    if request.security_master_value:
        client = AsyncOpenAI()
        compare_prompt = (
            f"Compare these two values for the '{request.field or 'field'}' field "
            f"of bond {isin}.\n\n"
            f"Security master value: {request.security_master_value}\n"
            f"Prospectus answer: {result.answer}\n\n"
            "Extract the specific value from the prospectus answer and determine "
            "if there is a meaningful mismatch between the two values.\n"
            "Return a JSON object with exactly two keys:\n"
            '- "mismatch": true if the values differ, false if they match\n'
            '- "prospectus_value": the specific value extracted from the prospectus '
            "answer (string), or null if not found\n"
            "Return only the JSON object."
        )

        compare_response = await client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": compare_prompt}],
        )
        raw = compare_response.choices[0].message.content or "{}"
        try:
            compare_data = json.loads(raw)
            mismatch_detected = bool(compare_data.get("mismatch", False))
            prospectus_value = compare_data.get("prospectus_value")
        except json.JSONDecodeError:
            mismatch_detected = False

    if mismatch_detected and request.field:
        recommendation = (
            f"Review {request.field} field in security master for ISIN {isin}"
        )

    return ValidationResponse(
        isin=isin,
        question=request.question,
        answer=result.answer,
        sources=result.sources,
        mismatch_detected=mismatch_detected,
        security_master_value=request.security_master_value,
        prospectus_value=prospectus_value,
        recommendation=recommendation,
        confidence=result.confidence,
    )
