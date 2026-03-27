# Bond Data Intelligence Platform

Unified query platform for time-split bond data — intelligent routing across dual MongoDB systems, with NLP query interface and a prospectus-grounded RAG validation layer on the roadmap.

---

## Architecture

```
Bloomberg Terminal
      ↓
Historical Data Pull
      ↓
Cleanse & Deduplicate          ← upstream, before platform
      ↓                                    ↓
Legacy MongoDB (port 27017)    Current MongoDB (port 27018)
[snapshots before 2026-01-01]  [snapshots from 2026-01-01]
      ↓                                    ↓
      └──────────── TemporalRouter ─────────┘
                          ↓
                  Unified API Response
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| API Framework | **FastAPI** | Async, fast, auto-generates docs |
| DB Driver | **Motor** | Async MongoDB driver for Python |
| Data Models | **Pydantic v2** | Validation + serialisation |
| Parallel Queries | **asyncio** | Both DBs queried simultaneously |
| Databases | **MongoDB x2** | One legacy, one current |
| Containerisation | **Docker Compose** | Spins up both DBs instantly |
| Testing | **pytest + pytest-asyncio** | Async test support |
| Server | **uvicorn** | ASGI server for FastAPI |
| Language | **Python 3.11** | |

---

## Query Routing Logic

```
User Request: GET /api/v1/bonds?isin=XS1234&from_date=2025-06-01&to_date=2026-03-01

TemporalRouter checks dates against CUTOFF_DATE (2026-01-01):

from_date < CUTOFF and to_date < CUTOFF  → Legacy DB only
from_date >= CUTOFF                       → Current DB only
from_date < CUTOFF and to_date >= CUTOFF → Both DBs in parallel (asyncio.gather)
                                            → Merge results
                                            → Sort by snapshot_date
                                            → Paginate
                                            → Return with sources: "both"
```

---

## Release Roadmap

| Release | Capability | AI Involvement |
|---------|-----------|---------------|
| Day 1 ✅ | REST API — ISIN + date range routing across dual MongoDB systems | None — pure intelligent routing |
| Day 2 🔜 | NLP free-text query interface | LLM extracts structured ISIN + date parameters from natural language |
| Day 3 🗺️ | Prospectus-Grounded Security Master Validation | Bond prospectuses/certificates ingested as PDFs → chunked and embedded into vector store → quants query call/put/conversion schedules in natural language → discrepancies between security master data and source documents surfaced automatically |

---

## Day 3 Vision — Prospectus-Grounded Security Master Validation

### The Problem

When data disputes arise in security master — particularly around call schedules, put
schedules, and conversion schedules — the final word has always been the original bond
prospectus or certificate. In practice, quants with access to these documents would
manually read through them to resolve mismatches.

Nobody had made those documents machine-queryable. Until now.

### What Day 3 Builds

Bond prospectuses and certificates (PDFs) are ingested into a vector store.
Quants query them in natural language. The RAG layer retrieves relevant sections
and generates a grounded answer — citing the exact prospectus clause.

### Example Queries

**Call schedule:**
> "What is the call schedule for ISIN XS1234567890?"
> → "Per Offering Circular (page 147): call dates 15 Jun 2024, 2025, 2026 at par + 0.5% premium. Security master shows par flat — mismatch flagged."

**Fixed coupon:**
> "What is the coupon rate and day count for ISIN XS1111111111?"
> → "Per Final Terms (page 12): 3.875% per annum, semi-annual, 30/360. Security master shows 3.850% — mismatch flagged."

**Floating coupon:**
> "What is the coupon formula for ISIN XS9999999999?"
> → "Per Offering Circular (page 34): 3M EURIBOR + 125bps, quarterly reset, Act/360, floor 0%. Security master spread shows 120bps — mismatch flagged."

### Document Types Supported

| Document | What it contains |
|----------|-----------------|
| Prospectus / Offering Circular | Full bond terms — call/put/conversion schedules, covenants |
| Final Terms | Specific economic terms for that ISIN |
| Pricing Supplement | Amendments to base prospectus |
| Corporate Action Notices | Restructurings, early redemptions, consent solicitations |

### Architecture

```
Bond Prospectus PDFs (per ISIN)
        ↓
PDF Ingestion Pipeline
        ↓
Chunking + Embedding (OpenAI / sentence-transformers)
        ↓
Vector Store (Chroma / Pinecone)
        ↓
RAG Query Engine
        ↓
POST /api/v3/validate/{isin}    ← natural language query against prospectus
        ↓
Grounded answer + prospectus citation + mismatch flag if differs from security master
```

See [`day3/README.md`](day3/README.md) for full Day 3 component documentation.
