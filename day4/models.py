"""
Day 4 — Pydantic v2 data models for the agentic reconciliation system.

All models use model_config = {} (Pydantic v2 pattern).
"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel


class IncomingRecord(BaseModel):
    """One row parsed from the uploaded CSV or JSON file."""

    isin: str
    snapshot_date: date
    issuer_name: str
    maturity_date: date
    coupon_rate: float
    currency: str
    face_value: float

    model_config = {}


class FieldMismatch(BaseModel):
    """A single field-level difference detected between incoming and master."""

    field: str
    incoming_value: Any
    master_value: Any

    model_config = {}


class ReconciliationEvent(BaseModel):
    """
    Emitted onto the event bus when at least one field mismatch is found.
    One event per incoming record that differs from the security master.
    """

    event_id: str          # uuid4
    isin: str
    snapshot_date: date
    incoming_record: IncomingRecord
    mismatches: list[FieldMismatch]
    emitted_at: datetime

    model_config = {}


class AgentRecommendation(BaseModel):
    """Per-field recommendation produced by the reconciliation agent."""

    field: str
    incoming_value: Any
    master_value: Any
    prospectus_value: str | None
    recommended_action: Literal["ACCEPT_INCOMING", "KEEP_MASTER", "MANUAL_REVIEW"]
    reasoning: str
    confidence: Literal["high", "medium", "low"]

    model_config = {}


class ReconciliationFinding(BaseModel):
    """
    Full agent output for one incoming record.
    Stored in the decision store and polled by the UI.
    """

    finding_id: str        # uuid4
    event_id: str
    isin: str
    snapshot_date: date
    recommendations: list[AgentRecommendation]
    overall_summary: str
    agent_phases: dict     # trace of Plan/Execute/Validate/Resolve phases
    created_at: datetime
    status: Literal["PENDING", "APPROVED", "REJECTED"]

    model_config = {}


class DecisionRequest(BaseModel):
    """User's accept/reject decision submitted via POST /api/v4/decide."""

    finding_id: str
    decision: Literal["APPROVE", "REJECT"]
    decided_by: str
    notes: str | None = None

    model_config = {}


class DecisionRecord(BaseModel):
    """
    Immutable audit log entry created on every user decision.
    Records are never updated or deleted.
    """

    decision_id: str       # uuid4
    finding_id: str
    isin: str
    decision: Literal["APPROVE", "REJECT"]
    decided_by: str
    notes: str | None
    fields_updated: list[str]   # fields actually changed (non-empty when APPROVE)
    decided_at: datetime

    model_config = {}
