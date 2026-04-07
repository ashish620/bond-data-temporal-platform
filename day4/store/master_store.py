"""
Day 4 — Security Master Store.

Motor-backed async CRUD for the `security_master` collection in Current MongoDB.
Used by the reconciliation agent to look up and update authoritative field values.
"""

import logging
from datetime import date

import motor.motor_asyncio

from app.config import CURRENT_DB_NAME, CURRENT_MONGO_URI
from app.models import BondSnapshot

logger = logging.getLogger(__name__)

_COLLECTION = "security_master"


class MasterStore:
    """
    Async MongoDB store for the security master (authoritative bond records).

    Collection: `security_master` in the Current MongoDB instance.
    """

    def __init__(self) -> None:
        self._client = motor.motor_asyncio.AsyncIOMotorClient(CURRENT_MONGO_URI)
        self._col = self._client[CURRENT_DB_NAME][_COLLECTION]

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get(self, isin: str, snapshot_date: date) -> BondSnapshot | None:
        """
        Retrieve the security master record for an ISIN on a given snapshot date.

        Returns:
            BondSnapshot if found, None otherwise.
        """
        doc = await self._col.find_one(
            {"isin": isin, "snapshot_date": snapshot_date.isoformat()}
        )
        if doc is None:
            return None
        doc.pop("_id", None)
        doc.setdefault("source", "current")
        return BondSnapshot(**doc)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def upsert(self, record: BondSnapshot) -> None:
        """
        Insert or replace the security master entry for (isin, snapshot_date).
        """
        doc = record.model_dump()
        doc["snapshot_date"] = doc["snapshot_date"].isoformat()
        doc["maturity_date"] = doc["maturity_date"].isoformat()

        await self._col.replace_one(
            {"isin": record.isin, "snapshot_date": record.snapshot_date.isoformat()},
            doc,
            upsert=True,
        )
        logger.debug("MasterStore: upserted %s / %s", record.isin, record.snapshot_date)

    async def update_fields(self, isin: str, snapshot_date: date, fields: dict) -> None:
        """
        Partial update — only set the keys present in *fields*.

        Args:
            isin:          ISIN of the bond.
            snapshot_date: Snapshot date of the record to update.
            fields:        Dict of field_name → new_value.
        """
        if not fields:
            return

        # Serialise date values so they can be stored as ISO strings
        serialised = {}
        for k, v in fields.items():
            if isinstance(v, date):
                serialised[k] = v.isoformat()
            else:
                serialised[k] = v

        await self._col.update_one(
            {"isin": isin, "snapshot_date": snapshot_date.isoformat()},
            {"$set": serialised},
        )
        logger.info(
            "MasterStore: updated fields %s for %s / %s",
            list(fields.keys()),
            isin,
            snapshot_date,
        )
