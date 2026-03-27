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
