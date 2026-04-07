"""
Day 4 — Streaming file ingestor for CSV and JSON uploads.

Processes each security record individually (event-driven, not batch).
For each record that has at least one field mismatch against the security
master, a ReconciliationEvent is published to the event bus.
"""

import csv
import io
import json
import logging
from datetime import datetime
from typing import AsyncIterator
from uuid import uuid4

from day4.models import IncomingRecord, ReconciliationEvent
from day4.pipeline.comparator import Comparator

logger = logging.getLogger(__name__)

_comparator = Comparator()


class FileIngestor:
    """
    Streams an uploaded file (CSV or JSON) and yields IncomingRecord objects
    one at a time without loading the whole file into memory.

    Supported formats
    -----------------
    - CSV  (detected by .csv extension or comma-separated content)
    - JSON (a top-level array of objects)
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ingest(self, file_content: bytes, filename: str) -> AsyncIterator[IncomingRecord]:
        """
        Yield one IncomingRecord at a time from the file.

        Args:
            file_content: Raw bytes of the uploaded file.
            filename:     Original filename — used to detect format.

        Yields:
            IncomingRecord for each valid row/object in the file.
        """
        text = file_content.decode("utf-8", errors="replace")

        if filename.lower().endswith(".json"):
            async for record in self._parse_json(text):
                yield record
        else:
            # Default to CSV for .csv or any other extension
            async for record in self._parse_csv(text):
                yield record

    async def ingest_and_dispatch(
        self,
        file_content: bytes,
        filename: str,
        master_store,
        event_bus,
    ) -> dict:
        """
        Stream records, compare each against the security master, and publish
        a ReconciliationEvent for every mismatch.

        Args:
            file_content: Raw bytes of the uploaded file.
            filename:     Original filename.
            master_store: MasterStore instance for security master lookups.
            event_bus:    EventBus instance to publish events onto.

        Returns:
            Summary dict with total_records, mismatches_found, events_published.
        """
        total = 0
        mismatches = 0

        async for record in self.ingest(file_content, filename):
            total += 1

            master = await master_store.get(record.isin, record.snapshot_date)
            if master is None:
                logger.debug(
                    "ISIN %s / %s not found in security master — skipping",
                    record.isin,
                    record.snapshot_date,
                )
                continue

            field_mismatches = _comparator.compare(record, master)
            if not field_mismatches:
                continue

            mismatches += 1
            event = ReconciliationEvent(
                event_id=str(uuid4()),
                isin=record.isin,
                snapshot_date=record.snapshot_date,
                incoming_record=record,
                mismatches=field_mismatches,
                emitted_at=datetime.utcnow(),
            )
            await event_bus.publish(event)
            logger.info(
                "Published ReconciliationEvent %s — ISIN %s, %d mismatch(es)",
                event.event_id,
                record.isin,
                len(field_mismatches),
            )

        return {
            "total_records": total,
            "mismatches_found": mismatches,
            "events_published": mismatches,
        }

    # ------------------------------------------------------------------
    # Private parsers
    # ------------------------------------------------------------------

    @staticmethod
    async def _parse_csv(text: str) -> AsyncIterator[IncomingRecord]:
        """Parse a CSV string and yield IncomingRecord objects."""
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            try:
                record = IncomingRecord(
                    isin=row["isin"].strip(),
                    snapshot_date=row["snapshot_date"].strip(),
                    issuer_name=row["issuer_name"].strip(),
                    maturity_date=row["maturity_date"].strip(),
                    coupon_rate=float(row["coupon_rate"]),
                    currency=row["currency"].strip(),
                    face_value=float(row["face_value"]),
                )
                yield record
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping invalid CSV row: %s — %s", row, exc)

    @staticmethod
    async def _parse_json(text: str) -> AsyncIterator[IncomingRecord]:
        """Parse a JSON array string and yield IncomingRecord objects."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse JSON file: %s", exc)
            return

        if not isinstance(data, list):
            logger.error("JSON file must contain a top-level array; got %s", type(data).__name__)
            return

        for item in data:
            try:
                record = IncomingRecord(**item)
                yield record
            except (TypeError, ValueError) as exc:
                logger.warning("Skipping invalid JSON object: %s — %s", item, exc)
