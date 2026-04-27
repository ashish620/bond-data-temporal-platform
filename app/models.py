"""
Pydantic v2 data models for Bond Data Intelligence Platform.
"""

from datetime import date

from pydantic import BaseModel


class BondSnapshot(BaseModel):
    """
    Represents a single bond snapshot from either Legacy or Current MongoDB.
    The `source` field records which DB the record originated from.
    """

    isin: str
    snapshot_date: date
    issuer_name: str
    maturity_date: date
    coupon_rate: float
    currency: str
    face_value: float
    source: str  # "legacy" or "current"

    model_config = {}


class BondQueryResponse(BaseModel):
    """Paginated response for bond snapshot queries."""

    data: list[BondSnapshot]
    total: int
    page: int
    page_size: int
    sources: str  # "legacy", "current", or "both"


class NLPQueryRequest(BaseModel):
    """Request body for NLP free-text bond query."""

    query: str  # e.g. "Show me XS1234567890 bonds from Q1 2025"
    page: int = 1
    page_size: int = 20


class NLPQueryResponse(BaseModel):
    """Response for NLP query — includes extracted parameters + bond data."""

    natural_query: str
    extracted_isin: str
    extracted_from_date: date
    extracted_to_date: date
    data: list[BondSnapshot]
    total: int
    page: int
    page_size: int
    sources: str
