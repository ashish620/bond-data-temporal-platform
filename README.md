# Bond Data Intelligence Platform

> Unified query platform for time-split bond data — intelligent routing across dual MongoDB, NLP query interface, RAG-grounded prospectus validation, and event-driven agentic reconciliation.

---

**TL;DR**
An AI-powered platform for financial security master systems that:
- unifies time-split data across dual MongoDB instances into a single seamless query interface
- enables natural language querying with LLM-extracted parameters
- validates data using RAG over PDF prospectus documents
- automates reconciliation using agentic workflows with human-in-the-loop approval

---

## Why This Exists

This project is inspired by common challenges in financial data systems, where security master data for bonds is often siloed across multiple systems with time boundaries, making unified querying difficult without manual intervention. Rather than proposing a simple data migration, this platform abstracts the time-split complexity entirely — routing queries intelligently across systems and merging results seamlessly into a single unified response.

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
- **One agent class, one per event** — a `ReconciliationAgent` is spawned per event; the event bus processes events sequentially, but within each agent run, source fetches (Phase 2) and field assessments (Phase 3) execute concurrently via `asyncio.gather`.
- **4-phase reasoning** — each agent reasons through Plan → Execute → Validate → Resolve, using tool-calls against legacy DB, current DB, and the prospectus RAG index.
- **Human-in-the-loop** — agent findings are stored as PENDING; a human operator calls `/api/v4/decide` to APPROVE or REJECT.
- **Immutable audit trail** — every decision (with timestamp, operator, and notes) is written to an append-only MongoDB collection and exposed via `/api/v4/audit`.

### Where AI Is Used (and Where It Is Not)

The system uses LLM reasoning at **four precise points** — not indiscriminately. This is intentional to keep costs bounded and latency predictable.

| Phase | Where LLM Is Used | What It Does |
|---|---|---|
| **Phase 1 — Plan** | `gpt-4o-mini` (JSON mode) | Given the mismatched fields and ISIN, decides which data sources are worth querying. Avoids fetching all three sources blindly — e.g. skips prospectus lookup for `face_value` mismatches where the document is unlikely to resolve the dispute. |
| **Phase 2 — Execute** | `text-embedding-ada-002` + `gpt-4o-mini` | Embeds per-field natural language questions for prospectus vector search, then generates a grounded answer from retrieved chunks. Only called for fields the Plan phase flagged as worth checking in the prospectus. |
| **Phase 3 — Validate** | `gpt-4o-mini` (JSON mode) | For each mismatched field, interprets all four data points — incoming value, master value, historical legacy snapshots, and prospectus answer — and decides which source is most likely correct and why. This is where mismatch interpretation happens: it doesn't just flag differences, it reasons about which side is right. |
| **Phase 4 — Resolve** | `gpt-4o-mini` | Synthesises all field-level assessments into a human-readable summary explaining the overall situation for the analyst reviewing the finding. |

Key design choices:
- **Interpretation, not just detection**: The comparator (pure Python, no LLM) detects mismatches. The agent interprets them — deciding which source to trust, what the likely cause is, and what action to recommend.
- **Reasoning is explicit**: Each `AgentRecommendation` includes a `reasoning` field containing the agent's natural-language explanation — the analyst sees exactly why the agent recommended `KEEP_MASTER` or `ACCEPT_INCOMING`, not just the outcome.
- **Source trust hierarchy**: The agent is given all four data points — prospectus answer, historical legacy values, current master value, and incoming value — and asked to determine which is most authoritative. The hierarchy (prospectus > historical consistency > current master > incoming value) emerges from the LLM's domain knowledge rather than being encoded in the prompt.

### Confidence Scoring

Every `AgentRecommendation` carries a `confidence` field: `"high"`, `"medium"`, or `"low"`. This is determined differently at each layer:

**RAG layer (Phase 2 — Prospectus lookup):**
Confidence is derived from the mean cosine distance of retrieved ChromaDB chunks:

| Mean Distance | Confidence |
|---|---|
| < 0.3 | `high` — prospectus excerpt is a strong match for the question |
| 0.3 – 0.6 | `medium` — relevant context found but not an exact match |
| > 0.6 | `low` — chunks retrieved are loosely related; answer may be unreliable |

**How confidence is assigned (Phase 4 — Resolve):**
`confidence` on each `AgentRecommendation` is derived from the Phase 3 recommended action and the Phase 2 prospectus RAG confidence. `assess_field_consistency()` returns a recommended action and reasoning but does not return a confidence label itself.

| Condition | Confidence |
|---|---|
| `MANUAL_REVIEW` action (any cause) | `"low"` |
| `ACCEPT_INCOMING` / `KEEP_MASTER` + high RAG confidence | `"high"` |
| `ACCEPT_INCOMING` / `KEEP_MASTER` + medium RAG confidence | `"medium"` |
| `ACCEPT_INCOMING` / `KEEP_MASTER` + low or absent RAG confidence | `"low"` |

### Failure Handling & Graceful Degradation

The agent is designed to never crash the pipeline. Each failure mode is handled explicitly:

| Failure Mode | Behaviour |
|---|---|
| **No prospectus ingested for ISIN** | `query_prospectus()` catches `ValueError` from `RAGQueryEngine` and returns `{"answer": "Not found in prospectus", "confidence": "low"}`. Agent continues with only DB sources. |
| **Legacy/Current DB returns no snapshots** | Agent proceeds with empty historical context. Phase 3 assess call receives an empty list for `legacy_values`. Confidence degrades to `low` or `medium`. |
| **LLM call fails (OpenAI timeout/rate limit)** | Each LLM call is wrapped in try/except. **Phase 1 failure:** falls back to querying all three sources (safe defaults — processing continues normally). **Phase 3 failure:** field assessment returns `MANUAL_REVIEW` with a failure reasoning; confidence is set to `"low"`. **Phase 4 failure:** a canned summary is substituted. The finding is saved to `DecisionStore` in all cases. |
| **Master record not found** | If `MasterStore.get()` returns `None` (ISIN+date not in security master), the record is treated as a new record — no mismatch is possible, no event is published. |
| **Malformed CSV/JSON row** | `FileIngestor` skips malformed rows and logs a warning. Processing continues for valid rows. |
| **Event bus subscriber crash** | Subscriber exceptions are caught and logged; the event bus loop continues processing subsequent events. Events are processed sequentially (one at a time), so a crash does not affect subsequent event handling. |

### Cost Awareness & Operational Considerations

#### The Cost Risk: One Agent Per Mismatch

The current design spawns one agent instance per mismatched record, with each instance making **3–5 LLM API calls** (Plan, per-field Validate × N, Resolve). For a file with 500 mismatches, that is potentially **1,500–2,500 LLM calls in a single ingest**.

At `gpt-4o-mini` pricing (~$0.15/1M input tokens), this is manageable for small files. But for large daily feeds with hundreds of mismatches, cost can compound quickly — especially when each Validate call sends the full context (incoming value + master value + historical snapshots + prospectus excerpt).

#### Mitigations Built In

| Mitigation | How It Works |
|---|---|
| **Phase 1 Planning limits tool calls** | The Plan phase decides which sources to query. If the LLM determines the prospectus is unlikely to help for a given field, `query_prospectus()` is never called — saving an embedding call + ChromaDB query + LLM generation call. |
| **Short-circuit on identical records** | The `Comparator` runs in pure Python with zero LLM cost. Records with no mismatches never trigger an agent at all. Only genuinely differing records enter the pipeline. |
| **gpt-4o-mini, not gpt-4o** | All agent reasoning uses `gpt-4o-mini` — approximately 15× cheaper than `gpt-4o` with sufficient reasoning quality for structured financial data comparison tasks. |

#### Recommended Mitigations for Production

These are not currently implemented but are the natural next steps for production deployment:

| Recommendation | Rationale |
|---|---|
| **Mismatch severity threshold** | Only trigger the agent if the mismatch exceeds a materiality threshold (e.g. coupon rate delta > 5bps, face value delta > 0.1%). Cosmetic differences (capitalisation, whitespace) are resolved by the comparator without an LLM. |
| **Batch mismatches by ISIN** | If 20 records for the same ISIN have mismatches, run one agent that fetches the ISIN's DB history and prospectus once, then assesses all 20 records in a single LLM call. Reduces API calls by up to 20×. |
| **Priority queue** | Process high-value ISINs (large face value, active bonds) first. Deprioritise or skip agent reasoning for low-value or matured bonds. |
| **Confidence-gated escalation** | Only call the expensive Validate + Resolve phases if Phase 1 planning returns `check_prospectus: true`. Records where both DB sources agree with each other (and only differ from incoming) can be resolved by rule with no further LLM cost. |
| **Cost cap per ingest** | Set a maximum agent invocation count per file upload. If the file contains more mismatches than the cap, queue the remainder for async processing or flag for batch review. |

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
