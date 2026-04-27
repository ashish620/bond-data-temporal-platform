"""
Day 4 — Immutable decision / audit log store.

Motor-backed async store for ReconciliationFinding and DecisionRecord documents
in the Current MongoDB instance.  Decision records are never updated or deleted.
"""

import logging

import motor.motor_asyncio

from app.config import CURRENT_DB_NAME, CURRENT_MONGO_URI
from day4.models import DecisionRecord, ReconciliationFinding

logger = logging.getLogger(__name__)

_FINDINGS_COLLECTION = "reconciliation_findings"
_DECISIONS_COLLECTION = "reconciliation_decisions"


class DecisionStore:
    """
    Async MongoDB store for reconciliation findings and user decisions.

    Collections
    -----------
    - ``reconciliation_findings``  — agent output awaiting or already reviewed
    - ``reconciliation_decisions`` — immutable audit log of every user decision
    """

    def __init__(self) -> None:
        self._client = motor.motor_asyncio.AsyncIOMotorClient(CURRENT_MONGO_URI)
        db = self._client[CURRENT_DB_NAME]
        self._findings_col = db[_FINDINGS_COLLECTION]
        self._decisions_col = db[_DECISIONS_COLLECTION]

    # ------------------------------------------------------------------
    # ReconciliationFinding CRUD
    # ------------------------------------------------------------------

    async def save_finding(self, finding: ReconciliationFinding) -> None:
        """Insert a new finding.  Uses finding_id as the document key."""
        doc = _finding_to_doc(finding)
        await self._findings_col.replace_one(
            {"finding_id": finding.finding_id}, doc, upsert=True
        )
        logger.debug("DecisionStore: saved finding %s", finding.finding_id)

    async def get_finding(self, finding_id: str) -> ReconciliationFinding | None:
        """Return the finding for the given ID, or None if not found."""
        doc = await self._findings_col.find_one({"finding_id": finding_id})
        if doc is None:
            return None
        doc.pop("_id", None)
        return _doc_to_finding(doc)

    async def list_findings(
        self,
        status: str | None = None,
        isin: str | None = None,
    ) -> list[ReconciliationFinding]:
        """
        List findings with optional filters.

        Args:
            status: Filter by PENDING / APPROVED / REJECTED.
            isin:   Filter by ISIN.
        """
        query: dict = {}
        if status:
            query["status"] = status
        if isin:
            query["isin"] = isin

        cursor = self._findings_col.find(query).sort("created_at", -1)
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(_doc_to_finding(doc))
        return results

    async def update_finding_status(self, finding_id: str, status: str) -> None:
        """Update the status field of an existing finding."""
        await self._findings_col.update_one(
            {"finding_id": finding_id},
            {"$set": {"status": status}},
        )
        logger.info("DecisionStore: finding %s → status %s", finding_id, status)

    # ------------------------------------------------------------------
    # DecisionRecord (immutable audit log)
    # ------------------------------------------------------------------

    async def save_decision(self, record: DecisionRecord) -> None:
        """Append a new decision record.  Never overwrites existing entries."""
        doc = _decision_to_doc(record)
        await self._decisions_col.insert_one(doc)
        logger.info(
            "DecisionStore: decision %s saved — %s by %s",
            record.decision_id,
            record.decision,
            record.decided_by,
        )

    async def list_decisions(self, isin: str | None = None) -> list[DecisionRecord]:
        """
        Return all decision records, optionally filtered by ISIN.

        Results are sorted by decided_at descending.
        """
        query: dict = {}
        if isin:
            query["isin"] = isin

        cursor = self._decisions_col.find(query).sort("decided_at", -1)
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(DecisionRecord(**doc))
        return results


# ---------------------------------------------------------------------------
# Serialisation helpers (Pydantic ↔ MongoDB document)
# ---------------------------------------------------------------------------


def _finding_to_doc(finding: ReconciliationFinding) -> dict:
    """Convert a ReconciliationFinding to a MongoDB-compatible document."""
    doc = finding.model_dump()
    # Store date/datetime as ISO strings for consistent querying
    doc["snapshot_date"] = doc["snapshot_date"].isoformat()
    doc["created_at"] = doc["created_at"].isoformat()
    return doc


def _doc_to_finding(doc: dict) -> ReconciliationFinding:
    """Reconstruct a ReconciliationFinding from a MongoDB document."""
    return ReconciliationFinding(**doc)


def _decision_to_doc(record: DecisionRecord) -> dict:
    """Convert a DecisionRecord to a MongoDB-compatible document."""
    doc = record.model_dump()
    doc["decided_at"] = doc["decided_at"].isoformat()
    return doc
