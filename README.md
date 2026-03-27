# Bond Data Intelligence Platform

> Unified query platform for time-split bond data — intelligent routing across dual MongoDB systems, with NLP query interface and RAG layer on the roadmap.

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
| Day 1 ✅ | REST API — ISIN + date range routing | None — pure intelligent routing |
| Day 2 🔜 | NLP free-text query interface | LLM extracts structured parameters |
| Day 3 🗺️ | RAG-powered answers | Vector retrieval + LLM generation over bond snapshots |

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

### `POST /api/v1/query` *(stubbed — Day 2)*

```bash
curl -X POST "http://localhost:8000/api/v1/query"
```

```json
{
  "message": "NLP query interface coming in Day 2 — LLM will extract structured parameters from natural language input",
  "status": "not_implemented"
}
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
│       └── bonds.py         ← API endpoints
│
├── tests/
│   ├── test_router.py       ← Routing logic and boundary condition tests
│   └── test_api.py          ← API endpoint and pagination tests
│
├── seed/
│   └── seed_data.py         ← Seed script for both MongoDB containers
│
├── docker-compose.yml       ← Two MongoDB containers + seed service
├── Dockerfile
├── requirements.txt         ← All Python dependencies
├── .env.example             ← MongoDB connection string placeholders
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
