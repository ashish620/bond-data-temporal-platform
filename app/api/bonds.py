"""
API endpoints for Bond Data Intelligence Platform.
"""

import os
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import BondQueryResponse, BondSnapshot, NLPQueryRequest, NLPQueryResponse
from app.nlp.extractor import NLPExtractor
from app.router import TemporalRouter

router = APIRouter()


def get_temporal_router() -> TemporalRouter:
    """Dependency — returns a shared TemporalRouter instance."""
    return TemporalRouter()


@router.get("/bonds", response_model=BondQueryResponse)
async def get_bonds(
    isin: Annotated[str, Query(description="Bond ISIN identifier e.g. XS1234567890")],
    from_date: Annotated[date, Query(description="Start of date range (YYYY-MM-DD)")],
    to_date: Annotated[date, Query(description="End of date range (YYYY-MM-DD)")],
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Results per page (max 100)")
    ] = 20,
    temporal_router: TemporalRouter = Depends(get_temporal_router),
) -> BondQueryResponse:
    """
    Query bond snapshots by ISIN and date range.

    Intelligently routes to Legacy DB, Current DB, or both depending on
    how the requested date range straddles the CUTOFF_DATE (2026-01-01).
    """
    if from_date > to_date:
        raise HTTPException(
            status_code=400, detail="from_date must not be after to_date"
        )

    all_snapshots, sources = await temporal_router.query(isin, from_date, to_date)

    total = len(all_snapshots)
    start = (page - 1) * page_size
    end = start + page_size
    page_data: list[BondSnapshot] = all_snapshots[start:end]

    return BondQueryResponse(
        data=page_data,
        total=total,
        page=page,
        page_size=page_size,
        sources=sources,
    )


@router.post("/query", response_model=NLPQueryResponse)
async def nlp_query(
    request: NLPQueryRequest,
    temporal_router: TemporalRouter = Depends(get_temporal_router),
) -> NLPQueryResponse:
    """
    Query bond snapshots using natural language.

    The LLM extracts the ISIN and date range from free-text input,
    then routes intelligently to Legacy DB, Current DB, or both via TemporalRouter.

    Example queries:
      - "Show me XS1234567890 bonds from Q1 2025"
      - "Get bond data for XS1234567890 between January and June 2026"
      - "XS1234567890 last 6 months"
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured")

    extractor = NLPExtractor()
    try:
        params = await extractor.extract(request.query)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    all_snapshots, sources = await temporal_router.query(
        params.isin, params.from_date, params.to_date
    )

    total = len(all_snapshots)
    start = (request.page - 1) * request.page_size
    end = start + request.page_size
    page_data: list[BondSnapshot] = all_snapshots[start:end]

    return NLPQueryResponse(
        natural_query=request.query,
        extracted_isin=params.isin,
        extracted_from_date=params.from_date,
        extracted_to_date=params.to_date,
        data=page_data,
        total=total,
        page=request.page,
        page_size=request.page_size,
        sources=sources,
    )
