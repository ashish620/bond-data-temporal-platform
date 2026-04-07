"""
FastAPI application entry point for Bond Data Intelligence Platform.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.bonds import router as bonds_router
from day3.api.validate import router as validate_router
from day4.api.reconcile import router as reconcile_router
from day4.pipeline.event_bus import event_bus

logger = logging.getLogger(__name__)

SEED_ISIN = "XS1234567890"


def _seed_if_needed() -> None:
    """
    Synchronous seed function — run in a thread pool executor to avoid
    blocking the async event loop.

    Checks if the prospectus for SEED_ISIN is already in ChromaDB.
    If not, generates the synthetic PDF and ingests it.
    """
    try:
        from day3.ingestion.document_store import DocumentStore
        from day3.ingestion.seed_sample import PDF_PATH, create_prospectus_pdf
        from day3.ingestion.pdf_ingester import PDFIngester

        store = DocumentStore()
        if store.collection_exists(SEED_ISIN):
            logger.info("Prospectus already seeded for %s — skipping", SEED_ISIN)
            return

        logger.info("Seeding prospectus for %s ...", SEED_ISIN)
        pdf_path = create_prospectus_pdf(PDF_PATH)
        ingester = PDFIngester()
        n = ingester.ingest_sync(str(pdf_path), SEED_ISIN, document_type="prospectus", force=True)  # force overwrites any partial data
        logger.info("Seeded prospectus for %s — %d chunks stored", SEED_ISIN, n)

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Prospectus auto-seed failed (non-fatal): %s. "
            "POST /api/v3/validate/{isin} will return 404 until seeded.",
            exc,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.

    On startup: auto-seeds the ChromaDB vector store with the synthetic
    prospectus PDF for SEED_ISIN if not already present. Runs the blocking
    seed work in a thread pool executor to avoid stalling the async event loop.
    On shutdown: nothing special needed.
    """
    # Run seed in thread pool so it doesn't block the event loop
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _seed_if_needed)
    # Start the Day 4 event bus background processing loop
    await event_bus.start()
    yield
    # Gracefully drain and stop the event bus on shutdown
    await event_bus.stop()


app = FastAPI(
    title="Bond Data Intelligence Platform",
    description=(
        "Unified query platform for time-split bond data — intelligent routing "
        "across dual MongoDB systems (Day 1), NLP query interface (Day 2), "
        "and RAG-grounded prospectus validation (Day 3 — live)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(bonds_router, prefix="/api/v1")
app.include_router(validate_router, prefix="/api/v3")
app.include_router(reconcile_router, prefix="/api/v4")
