# Bond Data Intelligence Platform

> Unified query platform for time-split bond data — intelligent routing across dual MongoDB, NLP query interface, RAG-grounded prospectus validation, event-driven agentic reconciliation, and immutable compliance audit trail.

---

**TL;DR**
An AI-powered platform for financial security master systems that:
- unifies time-split data across dual MongoDB instances into a single seamless query interface
- enables natural language querying with LLM-extracted parameters
- validates data using RAG over PDF prospectus documents
- automates reconciliation using agentic workflows with human-in-the-loop approval
- tracks every data override immutably with crypto-proof integrity (Day 5)

---

## Why This Exists

This project is inspired by common challenges in financial data systems, where security master data for bonds is often siloed across multiple systems with time boundaries, making unified querying [...]

---

## Why This Problem Is Hard

- **Data split across systems with inconsistent boundaries** — historical and live data live in separate databases with a hard time cutoff; no unified view exists without custom routing logic.
- **No single source of truth** — the security master, prospectus documents, legacy DB, and incoming feeds can all disagree, each for legitimate reasons.
- **Prospectus documents are unstructured** — authoritative bond terms are buried in PDFs; extracting them reliably requires vector search and grounded LLM generation.
- **Reconciliation requires contextual judgment** — knowing *which* value is correct for a given field demands reasoning about source reliability, not just flagging differences.
- **High risk of incorrect overrides without auditability** — automated decisions over financial master data must be human-approved and immutably logged.

---

## Design Philosophy

- **Deterministic where possible** — routing, comparison, and field matching are pure Python with zero LLM cost and fully predictable behaviour.
- **AI where necessary** — interpretation, source arbitration, and natural language explanation are delegated to the LLM only when rule-based logic cannot reason about context.
- **Human where required** — all agent recommendations require explicit operator approval before any master data is mutated; every decision is immutably logged.

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
                       ↓
              (Day 4: Agent Reconciliation)
                       ↓
              (Day 5: Immutable Audit Trail)
```

**Data integrity note:** Deduplication happens upstream during the Bloomberg data pull — before data enters this platform. Legacy MongoDB is guaranteed clean with no overlap against Current Mong[...]

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
| Blockchain (optional) | **Web3.py** | Hash immutability on Polygon/Ethereum |

---

## Release Roadmap

| Release | Capability | AI Involvement |
|---------|-----------|----------------|
| Day 1 ✅ | Structured API — `GET /api/v1/bonds` — explicit ISIN + date range, temporal routing across dual MongoDB | None — pure intelligent routing |
| Day 2 ✅ | NLP Query — `POST /api/v1/query` — free-text query, LLM extracts ISIN + date range | LLM extracts structured parameters from natural language |
| Day 3 ✅ | NLP + RAG — `POST /api/v3/validate/{isin}` — answers grounded in bond prospectus PDFs, mismatch detection vs security master | RAG over prospectus PDFs — vector retrieval + LLM[...]
| Day 4 ✅ | Event-Driven Agentic Reconciliation — `POST /api/v4/ingest` — streaming file ingestion, per-record mismatch detection, concurrent AI agent instances (Plan→Execute→Validate→Resolve) | 4-phase agent reasoning with contextual LLM calls |
| Day 5 🚀 | Immutable Audit Trail & Compliance — `GET /api/v5/audit-trail` — every data override cryptographically hashed, immutable logging, regulatory compliance | None — pure data integrity layer |

**Day 5 Status:** 📋 Specification complete. Implementation in progress.

---

## Quick Start

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

Operations teams receive daily feeds of security records from counterparties, custodians, or upstream systems. Reconciling each incoming record against the internal security master is tedious, er[...]

### Architecture

- **Event-driven, not batch** — records are streamed one-by-one through a `FileIngestor`; each mismatch immediately publishes a `ReconciliationEvent` to an async `EventBus`.
- **One agent class, one per event** — a `ReconciliationAgent` is spawned per event; the event bus processes events sequentially, but within each agent run, source fetches (Phase 2) and field a[...]
- **4-phase reasoning** — each agent reasons through Plan → Execute → Validate → Resolve, using tool-calls against legacy DB, current DB, and the prospectus RAG index.
- **Human-in-the-loop** — agent findings are stored as PENDING; a human operator calls `/api/v4/decide` to APPROVE or REJECT.
- **Immutable audit trail** — every decision (with timestamp, operator, and notes) is written to an append-only MongoDB collection and exposed via `/api/v4/audit`.

---

## Day 5 — Immutable Audit Trail & Compliance (`/api/v5`)

**See:** [`day5/SPECIFICATION.md`](day5/SPECIFICATION.md) for full details.

### The Problem It Solves

Every data override in Day 4 must be immutably logged for regulatory compliance (SEC Rule 17a-4, MiFID II, FINRA, SOX). Operations teams currently document these in Confluence (editable!) — which is a **compliance violation**.

Day 5 replaces Confluence with:
- ✅ Immutable, append-only audit trail (MongoDB)
- ✅ SHA-256 hashing for data integrity
- ✅ User attribution + timestamps
- ✅ Reason tracking (why was this override approved?)
- ✅ Optional blockchain backing (Polygon/Ethereum) for crypto-proof
- ✅ `/api/v5/audit-trail` & `/api/v5/compliance-report` for auditors

### Why Confluence Is Not Enough

| Aspect | Confluence | Day 5 |
|--------|-----------|-------|
| Can be edited? | ✅ Yes (compliance violation) | ❌ No (immutable) |
| Cryptographic proof? | ❌ No | ✅ Yes (SHA-256 + blockchain) |
| Regulatory admissible? | ⚠️ Weak | ✅ Yes |
| Audit query capability? | ❌ Manual search | ✅ `/api/v5/audit-trail` |

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
pytest tests/test_day5_audit.py -v
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
├── day5/                    ← Immutable audit trail & compliance
│   ├── store/               ← AuditStore (MongoDB + hashing)
│   ├── blockchain/          ← (Optional) Polygon/Ethereum backing
│   ├── api/                 ← /api/v5 endpoints
│   ├── SPECIFICATION.md     ← Full technical spec
│   └── README.md            ← Implementation guide
│
├── docs/
│   └── AUDIT_TRAIL_JUSTIFICATION.md ← Why immutable audit trails are essential
│
├── tests/
│   ├── test_router.py       ← Routing logic and boundary condition tests
│   ├── test_api.py          ← API endpoint and pagination tests
│   ├── test_nlp.py          ← NLP extractor tests
│   ├── test_rag.py          ← RAG pipeline tests
│   ├── test_day4_comparator.py ← Day 4 comparator unit tests
│   └── test_day5_audit.py   ← Day 5 audit trail tests
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

## Compliance & Regulatory Context

This platform is designed to meet:
- **MiFID II Art. 24** — Immutable trading & data records
- **SEC Rule 17a-4** — Audit trails for financial data mutations
- **SOX Section 302/404** — Data integrity certification
- **FINRA 4511(c)** — Immutable original entry records

**See:** [`docs/AUDIT_TRAIL_JUSTIFICATION.md`](docs/AUDIT_TRAIL_JUSTIFICATION.md)

---

## Next Steps (Day 5 Implementation)

- [ ] **Tier 1** (MongoDB + SHA-256) — Core audit trail with hashing
- [ ] **Tier 2** (Blockchain) — Write hashes to Polygon for crypto-proof
- [ ] **Tier 3** (Dashboard) — Compliance reporting UI for auditors

---

## License

MIT
