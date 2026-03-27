"""
API endpoints for Bond Data Intelligence Platform.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import BondQueryResponse, BondSnapshot
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


@router.post("/query")
async def nlp_query() -> dict:
    """
    Stubbed NLP query endpoint — coming in Day 2.

    # TODO Day 2: integrate LLM here to extract isin and date range from natural language
    """
    return {
        "message": (
            "NLP query interface coming in Day 2 — LLM will extract structured "
            "parameters from natural language input"
        ),
        "status": "not_implemented",
    }
