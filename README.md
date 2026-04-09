# Bond Data Intelligence Platform

> Unified query platform for time-split bond data — intelligent routing across dual MongoDB, NLP query interface, RAG-grounded prospectus validation, and event-driven agentic reconciliation.

---

## Why This Exists

This project originated from a real business problem identified and proposed at a previous firm — security master data for bonds was siloed across two systems with a hard time boundary, making unified querying impossible without manual intervention. Rather than proposing a simple data migration, this platform abstracts the time-split complexity entirely — routing queries intelligently across systems and merging results seamlessly into a single unified response.

---

## Data Architecture

```
Bloomberg Terminal
      ↓
Historical Data Pull
      ↓
Cleanse & Deduplicate (upstream — before platform)
      ↓                             ↓
Legacy MongoDB               Current MongoDB
(pre 2026-01-01)             (from 2026-01-01)
      ↓                             ↓
      └────────── TemporalRouter ───┘
                       ↓
             Unified API Response
```

**Data integrity note:** Deduplication happens upstream during the Bloomberg data pull — before data enters this platform. Legacy MongoDB is guaranteed clean with no overlap against Current MongoDB. The `TemporalRouter` simply merges and sorts results across the time boundary without additional deduplication.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| API Framework | **FastAPI** | Async REST API with auto-generated docs |
| DB Driver | **Motor** | Async MongoDB driver for Python |
| Data Models | **Pydantic v2** | Validation and serialisation |
| Parallel Queries | **asyncio** | Both DBs queried simultaneously when needed |
| Databases | **MongoDB × 2** | Legacy (port 27017) and Current (port 27018) |
| Containerisation | **Docker Compose** | Spins up full infrastructure instantly |
| Testing | **pytest + pytest-asyncio** | Async test support |
| Server | **uvicorn** | ASGI server for FastAPI |
| Language | **Python 3.11** | |

---

## Release Roadmap

| Release | Capability | AI Involvement |
|---------|-----------|----------------|
| Day 1 ✅ | Structured API — `GET /api/v1/bonds` — explicit ISIN + date range, temporal routing across dual MongoDB | None — pure intelligent routing |
| Day 2 ✅ | NLP Query — `POST /api/v1/query` — free-text query, LLM extracts ISIN + date range | LLM extracts structured parameters from natural language |
| Day 3 ✅ | NLP + RAG — `POST /api/v3/validate/{isin}` — answers grounded in bond prospectus PDFs, mismatch detection vs security master | RAG over prospectus PDFs — vector retrieval + LLM generation |
| Day 4 ✅ | Event-Driven Agentic Reconciliation — `POST /api/v4/ingest` — streaming file ingestion, per-record mismatch detection, concurrent AI agent instances (Plan→Execute→Validate→Resolve), human approval workflow, immutable audit trail | Agentic AI — LLM-driven 4-phase reasoning per record, tool-calling over legacy DB, current DB and prospectus |

---

## Setup

### Prerequisites
- Docker and Docker Compose installed

### Run with Docker Compose

```bash
# Clone the repo
git clone https://github.com/ashish620/bond-data-intelligence-platform.git
cd bond-data-intelligence-platform

# Copy environment variables
cp .env.example .env

# Start all services (MongoDB ×2 + seed data + API)
docker compose up --build
```

The API will be available at **http://localhost:8000**.

Interactive API docs (Swagger UI): **http://localhost:8000/docs**

---

## API Documentation

### `GET /api/v1/bonds`

Query bond snapshots by ISIN and date range.

**Query parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `isin` | ✅ | — | Bond ISIN identifier e.g. `XS1234567890` |
| `from_date` | ✅ | — | Start date `YYYY-MM-DD` |
| `to_date` | ✅ | — | End date `YYYY-MM-DD` |
| `page` | ❌ | `1` | Page number |
| `page_size` | ❌ | `20` | Results per page (max 100) |

**Example — Legacy DB only (pre-2026):**

```bash
curl "http://localhost:8000/api/v1/bonds?isin=XS1234567890&from_date=2025-01-01&to_date=2025-12-31"
```

```json
{
  "data": [
    {
      "isin": "XS1234567890",
      "snapshot_date": "2025-01-15",
      "issuer_name": "Acme Corp",
      "maturity_date": "2030-01-15",
      "coupon_rate": 3.5,
      "currency": "USD",
      "face_value": 1000.0,
      "source": "legacy"
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 20,
  "sources": "legacy"
}
```

**Example — Both DBs (query spans 2026-01-01):**

```bash
curl "http://localhost:8000/api/v1/bonds?isin=XS1234567890&from_date=2025-06-01&to_date=2026-06-30"
```

```json
{
  "data": [...],
  "total": 4,
  "page": 1,
  "page_size": 20,
  "sources": "both"
}
```

### `POST /api/v1/query`

Send a free-text natural language query. The LLM extracts the ISIN and date range, then routes to the appropriate MongoDB instance(s).

**Example:**

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me XS1234567890 bond data from January to June 2025"}'
```

```json
{
  "extracted_isin": "XS1234567890",
  "extracted_from_date": "2025-01-01",
  "extracted_to_date": "2025-06-30",
  "natural_query": "Show me XS1234567890 bond data from January to June 2025",
  "sources": "legacy",
  "data": [
    {
      "isin": "XS1234567890",
      "snapshot_date": "2025-01-15",
      "issuer_name": "Acme Corp",
      "maturity_date": "2030-01-15",
      "coupon_rate": 3.5,
      "currency": "USD",
      "face_value": 1000.0,
      "source": "legacy"
    }
  ]
}
```

---

## Day 4 — Agentic Reconciliation (`/api/v4`)

### The Problem It Solves

Operations teams receive daily feeds of security records from counterparties, custodians, or upstream systems. Reconciling each incoming record against the internal security master is tedious, error-prone, and slow when done manually. Day 4 automates this entirely — streaming each record, detecting mismatches field-by-field, spawning a concurrent AI agent per mismatch, and surfacing a human-approved resolution with an immutable audit trail.

### Architecture

- **Event-driven, not batch** — records are streamed one-by-one through a `FileIngestor`; each mismatch immediately publishes a `ReconciliationEvent` to an async `EventBus`.
- **One agent class, N concurrent instances** — a `ReconciliationAgent` is spawned per event; instances run concurrently via `asyncio`.
- **4-phase reasoning** — each agent reasons through Plan → Execute → Validate → Resolve, using tool-calls against legacy DB, current DB, and the prospectus RAG index.
- **Human-in-the-loop** — agent findings are stored as PENDING; a human operator calls `/api/v4/decide` to APPROVE or REJECT.
- **Immutable audit trail** — every decision (with timestamp, operator, and notes) is written to an append-only MongoDB collection and exposed via `/api/v4/audit`.

### `POST /api/v4/ingest`

Upload a CSV or JSON file of security records. Records are streamed one-by-one. For each record with a mismatch against the security master, a `ReconciliationEvent` is published and a concurrent AI agent instance is spawned.

**Example:**

```bash
curl -X POST http://localhost:8000/api/v4/ingest \
  -F "file=@bonds.csv"
```

```json
{
  "total_records": 5,
  "mismatches_found": 2,
  "events_published": 2,
  "message": "Ingested 5 record(s); 2 mismatch(es) found; 2 reconciliation event(s) published."
}
```

### `GET /api/v4/findings`

List agent findings awaiting approval. Filter by `status` (PENDING/APPROVED/REJECTED) and/or `isin`.

```bash
curl "http://localhost:8000/api/v4/findings?status=PENDING"
```

### `POST /api/v4/decide`

Accept or reject an agent recommendation. On APPROVE, master data is updated. All decisions are immutably logged.

```bash
curl -X POST http://localhost:8000/api/v4/decide \
  -H "Content-Type: application/json" \
  -d '{"finding_id":"abc123","decision":"APPROVE","decided_by":"analyst1","notes":"Verified"}'
```

### `GET /api/v4/audit`

Full immutable audit trail of all decisions ever made.

```bash
curl http://localhost:8000/api/v4/audit
```

---

## Running Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_router.py -v
pytest tests/test_api.py -v
pytest tests/test_nlp.py -v
pytest tests/test_rag.py -v
pytest tests/test_day4_comparator.py -v
```

Tests do **not** require running MongoDB instances — all DB interactions are mocked.

---

## Project Structure

```
bond-data-intelligence-platform/
│
├── app/
│   ├── main.py              ← FastAPI app entry point
│   ├── config.py            ← CUTOFF_DATE and DB settings
│   ├── router.py            ← TemporalRouter core engine
│   ├── models.py            ← Bond data models (Pydantic v2)
│   └── api/
│       └── bonds.py         ← API endpoints (Day 1 + Day 2)
│
├── day3/                    ← RAG prospectus validation
│   ├── ingestion/           ← PDF ingestion + ChromaDB
│   ├── rag/                 ← RAG query engine
│   └── api/                 ← POST /api/v3/validate/{isin}
│
├── day4/                    ← Event-driven agentic reconciliation
│   ├── agent/               ← ReconciliationAgent (4-phase)
│   ├── pipeline/            ← EventBus, FileIngestor, Comparator
│   ├── store/               ← MasterStore + DecisionStore (MongoDB)
│   └── api/                 ← /api/v4 endpoints
│
├── tests/
│   ├── test_router.py       ← Routing logic and boundary condition tests
│   ├── test_api.py          ← API endpoint and pagination tests
│   ├── test_nlp.py          ← NLP extractor tests
│   ├── test_rag.py          ← RAG pipeline tests
│   └── test_day4_comparator.py ← Day 4 comparator unit tests
│
├── seed/
│   └── seed_data.py         ← Seed script for both MongoDB containers
│
├── docker-compose.yml       ← Two MongoDB containers + seed service + API
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---

## Routing Logic

```
Query: isin=XS1234567890, from_date=2025-06-01, to_date=2026-03-01

TemporalRouter checks against CUTOFF_DATE = 2026-01-01:

from_date < CUTOFF AND to_date < CUTOFF  → Legacy DB only   → sources: "legacy"
from_date >= CUTOFF                       → Current DB only  → sources: "current"
from_date < CUTOFF AND to_date >= CUTOFF → Both in parallel  → sources: "both"
                                            ↓
                                      asyncio.gather()
                                            ↓
                                    Merge + sort by date
                                            ↓
                                    Paginate + respond
```

---

## License

MIT
