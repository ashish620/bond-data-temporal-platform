"""
TemporalRouter — core routing engine for Bond Data Intelligence Platform.

Routes bond snapshot queries intelligently across two MongoDB instances
based on the CUTOFF_DATE boundary (2026-01-01).

BBG upstream clean ingestion contract:
    Legacy MongoDB is pre-cleansed and deduplicated during the Bloomberg
    historical data pull — BEFORE ingestion into this platform. Therefore,
    there is guaranteed zero overlap between Legacy and Current DBs.
    The router simply merges and sorts results; no deduplication is needed.
"""

import asyncio
from datetime import date

import motor.motor_asyncio

from app.config import (
    BONDS_COLLECTION,
    CURRENT_DB_NAME,
    CURRENT_MONGO_URI,
    CUTOFF_DATE,
    LEGACY_DB_NAME,
    LEGACY_MONGO_URI,
)
from app.models import BondSnapshot


class TemporalRouter:
    """
    Routes queries to Legacy DB, Current DB, or both, depending on the
    date range relative to CUTOFF_DATE = 2026-01-01.

    Routing rules:
        from_date < CUTOFF and to_date < CUTOFF  → Legacy DB only
        from_date >= CUTOFF                       → Current DB only
        from_date < CUTOFF and to_date >= CUTOFF → Both DBs in parallel
    """

    def __init__(self) -> None:
        self._legacy_client = motor.motor_asyncio.AsyncIOMotorClient(LEGACY_MONGO_URI)
        self._current_client = motor.motor_asyncio.AsyncIOMotorClient(CURRENT_MONGO_URI)
        self._legacy_col = self._legacy_client[LEGACY_DB_NAME][BONDS_COLLECTION]
        self._current_col = self._current_client[CURRENT_DB_NAME][BONDS_COLLECTION]

    def _determine_sources(self, from_date: date, to_date: date) -> str:
        """Return which DB(s) to query based on the date range."""
        if from_date < CUTOFF_DATE and to_date < CUTOFF_DATE:
            return "legacy"
        if from_date >= CUTOFF_DATE:
            return "current"
        # from_date < CUTOFF and to_date >= CUTOFF
        return "both"

    async def _fetch_from_collection(
        self,
        collection: motor.motor_asyncio.AsyncIOMotorCollection,
        isin: str,
        from_date: date,
        to_date: date,
        source_label: str,
    ) -> list[BondSnapshot]:
        """Fetch bond snapshots from a single collection."""
        query = {
            "isin": isin,
            "snapshot_date": {
                "$gte": from_date.isoformat(),
                "$lte": to_date.isoformat(),
            },
        }
        cursor = collection.find(query)
        results: list[BondSnapshot] = []
        async for doc in cursor:
            doc.pop("_id", None)
            doc["source"] = source_label
            results.append(BondSnapshot(**doc))
        return results

    async def query(
        self,
        isin: str,
        from_date: date,
        to_date: date,
    ) -> tuple[list[BondSnapshot], str]:
        """
        Query bond snapshots for the given ISIN and date range.

        Returns a tuple of (snapshots sorted by snapshot_date, sources string).
        """
        sources = self._determine_sources(from_date, to_date)

        if sources == "legacy":
            snapshots = await self._fetch_from_collection(
                self._legacy_col, isin, from_date, to_date, "legacy"
            )

        elif sources == "current":
            snapshots = await self._fetch_from_collection(
                self._current_col, isin, from_date, to_date, "current"
            )

        else:
            # Both DBs — query in parallel using asyncio.gather()
            # BBG upstream clean ingestion contract guarantees no overlap
            # between legacy and current snapshots; simple merge is sufficient.
            legacy_results, current_results = await asyncio.gather(
                self._fetch_from_collection(
                    self._legacy_col, isin, from_date, to_date, "legacy"
                ),
                self._fetch_from_collection(
                    self._current_col, isin, from_date, to_date, "current"
                ),
            )
            snapshots = legacy_results + current_results

        # Sort merged results by snapshot_date ascending
        snapshots.sort(key=lambda s: s.snapshot_date)
        return snapshots, sources

    def close(self) -> None:
        """Close MongoDB client connections."""
        self._legacy_client.close()
        self._current_client.close()
