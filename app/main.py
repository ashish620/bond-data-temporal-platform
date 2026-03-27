"""
FastAPI application entry point for Bond Data Intelligence Platform.
"""

from fastapi import FastAPI

from app.api.bonds import router as bonds_router

app = FastAPI(
    title="Bond Data Intelligence Platform",
    description=(
        "Unified query platform for time-split bond data — intelligent routing "
        "across dual MongoDB systems, with NLP query interface and RAG layer on the roadmap."
    ),
    version="1.0.0",
)

app.include_router(bonds_router, prefix="/api/v1")
