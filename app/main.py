"""
FastAPI application entry point for Bond Data Intelligence Platform.
"""

from fastapi import FastAPI

from app.api.bonds import router as bonds_router
from day3.api.validate import router as validate_router

app = FastAPI(
    title="Bond Data Intelligence Platform",
    description=(
        "Unified query platform for time-split bond data — intelligent routing "
        "across dual MongoDB systems (Day 1), NLP query interface (Day 2), "
        "and RAG-grounded prospectus validation (Day 3 — live)."
    ),
    version="1.0.0",
)

app.include_router(bonds_router, prefix="/api/v1")
app.include_router(validate_router, prefix="/api/v3")
