"""
Day 4 — Reconciliation API Router

Mounted at /api/v4 by app/main.py.

Endpoints
---------
POST  /api/v4/ingest    — upload CSV/JSON, trigger streaming reconciliation pipeline
GET   /api/v4/findings  — list agent findings (filter by status / ISIN)
POST  /api/v4/decide    — accept or reject an agent recommendation
GET   /api/v4/audit     — full immutable audit trail
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, UploadFile

from app.router import TemporalRouter
from day3.ingestion.document_store import DocumentStore
from day3.rag.query_engine import RAGQueryEngine
from day4.agent.reconciliation_agent import ReconciliationAgent
from day4.models import (
    DecisionRecord,
    DecisionRequest,
    ReconciliationEvent,
    ReconciliationFinding,
)
from day4.pipeline.event_bus import event_bus
from day4.pipeline.ingestor import FileIngestor
from day4.store.decision_store import DecisionStore
from day4.store.master_store import MasterStore

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Lazy singletons — created once per process
# ---------------------------------------------------------------------------

_master_store: MasterStore | None = None
_decision_store: DecisionStore | None = None
_temporal_router: TemporalRouter | None = None
_rag_engine: RAGQueryEngine | None = None
_ingestor = FileIngestor()


def _get_master_store() -> MasterStore:
    global _master_store
    if _master_store is None:
        _master_store = MasterStore()
    return _master_store


def _get_decision_store() -> DecisionStore:
    global _decision_store
    if _decision_store is None:
        _decision_store = DecisionStore()
    return _decision_store


def _get_temporal_router() -> TemporalRouter:
    global _temporal_router
    if _temporal_router is None:
        _temporal_router = TemporalRouter()
    return _temporal_router


def _get_rag_engine() -> RAGQueryEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGQueryEngine(DocumentStore())
    return _rag_engine


# ---------------------------------------------------------------------------
# Event bus handler — spawns one ReconciliationAgent per event
# ---------------------------------------------------------------------------


async def _handle_reconciliation_event(event: ReconciliationEvent) -> None:
    """
    Subscriber registered with the event bus.

    Creates a ReconciliationAgent, runs all 4 phases, and saves the resulting
    finding to the decision store.
    """
    try:
        agent = ReconciliationAgent(
            event=event,
            router=_get_temporal_router(),
            rag_engine=_get_rag_engine(),
        )
        finding = await agent.run()
        await _get_decision_store().save_finding(finding)
        logger.info(
            "Finding %s saved for event %s (ISIN %s)",
            finding.finding_id,
            event.event_id,
            event.isin,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "Reconciliation agent failed for event %s (ISIN %s)",
            event.event_id,
            event.isin,
        )


# Register the handler once at module import time
event_bus.subscribe(_handle_reconciliation_event)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/ingest")
async def ingest(file: UploadFile) -> dict:
    """
    Upload a CSV or JSON file of security records.

    Each record is compared against the security master.  For every record
    with at least one field mismatch a ReconciliationEvent is published to the
    event bus, which spawns a concurrent ReconciliationAgent instance.

    Returns a summary of how many records were processed and how many
    mismatches were found.
    """
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Filename is required.")

    content = await file.read()
    summary = await _ingestor.ingest_and_dispatch(
        file_content=content,
        filename=file.filename,
        master_store=_get_master_store(),
        event_bus=event_bus,
    )
    summary["message"] = (
        f"Ingested {summary['total_records']} record(s); "
        f"{summary['mismatches_found']} mismatch(es) found; "
        f"{summary['events_published']} reconciliation event(s) published."
    )
    return summary


@router.get("/findings", response_model=list[ReconciliationFinding])
async def list_findings(
    status: str | None = Query(default=None, description="PENDING | APPROVED | REJECTED"),
    isin: str | None = Query(default=None, description="Filter by ISIN"),
) -> list[ReconciliationFinding]:
    """
    Return agent findings awaiting (or already receiving) a user decision.

    Optionally filter by status and/or ISIN.
    """
    return await _get_decision_store().list_findings(status=status, isin=isin)


@router.post("/decide", response_model=DecisionRecord)
async def decide(request: DecisionRequest) -> DecisionRecord:
    """
    Accept or reject an agent recommendation.

    - APPROVE: applies all ACCEPT_INCOMING field updates to the security master
               and creates an immutable DecisionRecord.
    - REJECT:  creates a DecisionRecord without changing master data.

    Returns the saved DecisionRecord (audit log entry).
    """
    store = _get_decision_store()

    finding = await store.get_finding(request.finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail=f"Finding {request.finding_id!r} not found.")

    fields_updated: list[str] = []

    if request.decision == "APPROVE":
        # Apply ACCEPT_INCOMING recommendations to the security master
        fields_to_update: dict = {}
        for rec in finding.recommendations:
            if rec.recommended_action == "ACCEPT_INCOMING":
                fields_to_update[rec.field] = rec.incoming_value
                fields_updated.append(rec.field)

        if fields_to_update:
            await _get_master_store().update_fields(
                isin=finding.isin,
                snapshot_date=finding.snapshot_date,
                fields=fields_to_update,
            )

    decision_record = DecisionRecord(
        decision_id=str(uuid4()),
        finding_id=request.finding_id,
        isin=finding.isin,
        decision=request.decision,
        decided_by=request.decided_by,
        notes=request.notes,
        fields_updated=fields_updated,
        decided_at=datetime.now(timezone.utc),
    )

    await store.save_decision(decision_record)
    await store.update_finding_status(
        request.finding_id,
        "APPROVED" if request.decision == "APPROVE" else "REJECTED",
    )

    logger.info(
        "Decision %s: %s by %s for finding %s (ISIN %s)",
        decision_record.decision_id,
        request.decision,
        request.decided_by,
        request.finding_id,
        finding.isin,
    )

    return decision_record


@router.get("/audit", response_model=list[DecisionRecord])
async def audit(
    isin: str | None = Query(default=None, description="Filter by ISIN"),
) -> list[DecisionRecord]:
    """
    Return the full immutable audit trail of user decisions.

    Optionally filter by ISIN.  Results are ordered by decided_at descending.
    """
    return await _get_decision_store().list_decisions(isin=isin)
