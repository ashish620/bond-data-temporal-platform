# Day 4 — Event-Driven Agentic Reconciliation System

Day 4 extends the Bond Data Intelligence Platform with a fully event-driven,
agentic reconciliation engine that detects field-level mismatches in incoming
security files and, for each mismatch, spawns a concurrent AI agent instance
that reasons over multiple data sources and generates a recommendation for
user approval.

---

## Architecture

```
                        ┌─────────────────────────────────────┐
                        │  POST /api/v4/ingest (UploadFile)   │
                        └──────────────┬──────────────────────┘
                                       │  file bytes
                                       ▼
                             ┌──────────────────┐
                             │   FileIngestor   │  streaming, record-by-record
                             └────────┬─────────┘
                                      │  IncomingRecord  (one at a time)
                                      ▼
                            ┌──────────────────────┐
                            │    MasterStore.get()  │  security_master collection
                            └──────────┬────────────┘
                                       │  BondSnapshot or None
                                       ▼
                             ┌──────────────────┐
                             │    Comparator    │  field-level diff
                             └────────┬─────────┘
                                      │ list[FieldMismatch]
                          mismatches? │
                 ┌─────── YES ────────┘
                 │
                 ▼
       ┌──────────────────────┐
       │  EventBus.publish()  │  asyncio.Queue, fan-out to subscribers
       └──────────┬───────────┘
                  │  ReconciliationEvent
                  ▼
   ┌──────────────────────────────────────────────────┐
   │  _handle_reconciliation_event  (subscriber)      │
   │                                                  │
   │   ┌──────────────────────────────────────────┐   │
   │   │  ReconciliationAgent.run()               │   │  ← one instance per event
   │   │                                          │   │    many run concurrently
   │   │  Phase 1 — PLAN                          │   │
   │   │    LLM decides which sources to query    │   │
   │   │                                          │   │
   │   │  Phase 2 — EXECUTE (asyncio.gather)      │   │
   │   │    fetch_from_legacy_db()                │   │
   │   │    fetch_from_current_db()               │   │
   │   │    query_prospectus() × N fields         │   │
   │   │                                          │   │
   │   │  Phase 3 — VALIDATE (asyncio.gather)     │   │
   │   │    assess_field_consistency() × N fields │   │
   │   │                                          │   │
   │   │  Phase 4 — RESOLVE                       │   │
   │   │    Build AgentRecommendation objects     │   │
   │   │    LLM generates overall_summary         │   │
   │   └──────────────────┬───────────────────────┘   │
   │                      │  ReconciliationFinding     │
   └──────────────────────┼──────────────────────────-┘
                          │
                          ▼
              ┌────────────────────────┐
              │  DecisionStore         │
              │  .save_finding()       │  reconciliation_findings collection
              └────────────┬───────────┘
                           │
                           ▼
          ┌────────────────────────────────┐
          │  GET /api/v4/findings          │  UI polls for PENDING findings
          └────────────────┬───────────────┘
                           │  user reviews recommendations
                           ▼
          ┌────────────────────────────────┐
          │  POST /api/v4/decide           │  APPROVE or REJECT
          └────────────────┬───────────────┘
                           │
               ┌───────────┴───────────┐
               │ APPROVE               │ REJECT
               ▼                       ▼
  MasterStore.update_fields()   log only (no DB change)
               │                       │
               └───────────┬───────────┘
                           ▼
              ┌────────────────────────┐
              │  DecisionStore         │
              │  .save_decision()      │  reconciliation_decisions (immutable)
              └────────────────────────┘
                           │
                           ▼
          ┌────────────────────────────────┐
          │  GET /api/v4/audit             │  full audit trail
          └────────────────────────────────┘
```

---

## The 4-Phase Agent Design

One `ReconciliationAgent` instance handles exactly one `ReconciliationEvent`
(i.e., one incoming record with at least one mismatch).  Many instances run
**concurrently** via `asyncio.gather` in the event bus subscriber — one per
mismatched record in the uploaded file.

### Phase 1 — PLAN

The LLM (gpt-4o-mini) receives the list of mismatched fields and the ISIN,
and decides which data sources are worth querying:

```json
{
  "check_legacy": true,
  "check_current": true,
  "check_prospectus": true,
  "fields_to_prospect": ["coupon_rate", "maturity_date"]
}
```

### Phase 2 — EXECUTE

Based on the plan, the agent concurrently fetches:
- **Legacy DB** snapshots (2020-01-01 → CUTOFF_DATE - 1 day) via `TemporalRouter`
- **Current DB** snapshots (CUTOFF_DATE → today) via `TemporalRouter`
- **Prospectus** answers (one per mismatched field) via `RAGQueryEngine`

All three fetches run concurrently with `asyncio.gather`.  If any source is
unavailable (e.g. no prospectus ingested), it degrades gracefully.

### Phase 3 — VALIDATE

For each mismatched field, `assess_field_consistency()` is called with all
four data points: incoming value, master value, historical legacy values, and
prospectus answer.  All field assessments run concurrently via `asyncio.gather`.

### Phase 4 — RESOLVE

Assessment results are converted to `AgentRecommendation` objects with one of
three actions: `ACCEPT_INCOMING`, `KEEP_MASTER`, or `MANUAL_REVIEW`.  An
LLM-generated natural-language summary is appended.

---

## API Endpoints

### `POST /api/v4/ingest`

Upload a CSV or JSON file of security records.

**Request:** `multipart/form-data` with field `file`.

**CSV format:**
```csv
isin,snapshot_date,issuer_name,maturity_date,coupon_rate,currency,face_value
XS1234567890,2026-03-01,ACME Corp,2030-06-15,4.5,USD,1000000.0
XS1234567890,2026-03-01,ACME Corp,2030-06-15,5.0,EUR,1000000.0
```

**JSON format:**
```json
[
  {
    "isin": "XS1234567890",
    "snapshot_date": "2026-03-01",
    "issuer_name": "ACME Corp",
    "maturity_date": "2030-06-15",
    "coupon_rate": 5.0,
    "currency": "EUR",
    "face_value": 1000000.0
  }
]
```

**Response:**
```json
{
  "total_records": 2,
  "mismatches_found": 1,
  "events_published": 1,
  "message": "Ingested 2 record(s); 1 mismatch(es) found; 1 reconciliation event(s) published."
}
```

---

### `GET /api/v4/findings`

List agent findings.  Optional query parameters: `status` (PENDING / APPROVED / REJECTED),
`isin`.

**Response:** Array of `ReconciliationFinding` objects.

```json
[
  {
    "finding_id": "abc123...",
    "event_id": "evt456...",
    "isin": "XS1234567890",
    "snapshot_date": "2026-03-01",
    "recommendations": [
      {
        "field": "coupon_rate",
        "incoming_value": 5.0,
        "master_value": 4.5,
        "prospectus_value": "4.5%",
        "recommended_action": "KEEP_MASTER",
        "reasoning": "Prospectus confirms 4.5% — incoming value appears incorrect.",
        "confidence": "high"
      }
    ],
    "overall_summary": "One coupon rate mismatch detected for XS1234567890...",
    "agent_phases": {...},
    "created_at": "2026-04-07T10:00:00",
    "status": "PENDING"
  }
]
```

---

### `POST /api/v4/decide`

Accept or reject an agent recommendation.

**Request body:**
```json
{
  "finding_id": "abc123...",
  "decision": "APPROVE",
  "decided_by": "ashish620",
  "notes": "Confirmed with front office — keeping master value."
}
```

**Response:** `DecisionRecord` (immutable audit log entry).

```json
{
  "decision_id": "dec789...",
  "finding_id": "abc123...",
  "isin": "XS1234567890",
  "decision": "APPROVE",
  "decided_by": "ashish620",
  "notes": "Confirmed with front office — keeping master value.",
  "fields_updated": [],
  "decided_at": "2026-04-07T10:05:00"
}
```

---

### `GET /api/v4/audit`

Full immutable audit trail.  Optional query parameter: `isin`.

**Response:** Array of `DecisionRecord` objects, ordered by `decided_at` descending.

---

## Testing with a Sample CSV

1. **Seed the security master** — insert a record into `security_master` in the
   current MongoDB instance with the ISIN and snapshot date you will upload.

2. **Create a sample CSV** that differs in at least one field:

```csv
isin,snapshot_date,issuer_name,maturity_date,coupon_rate,currency,face_value
XS1234567890,2026-03-01,ACME Corp,2030-06-15,5.0,USD,1000000.0
```

3. **Upload via curl:**
```bash
curl -X POST http://localhost:8000/api/v4/ingest \
  -F "file=@sample.csv"
```

4. **Poll for findings:**
```bash
curl http://localhost:8000/api/v4/findings?status=PENDING
```

5. **Approve a finding:**
```bash
curl -X POST http://localhost:8000/api/v4/decide \
  -H "Content-Type: application/json" \
  -d '{"finding_id":"<id>","decision":"APPROVE","decided_by":"analyst1"}'
```

6. **Review the audit trail:**
```bash
curl http://localhost:8000/api/v4/audit
```

---

## Decision / Audit Trail

Every `POST /api/v4/decide` call creates an immutable `DecisionRecord` in the
`reconciliation_decisions` MongoDB collection.  Records are **never updated or
deleted**.  The `fields_updated` array lists which master data fields were
actually changed (non-empty only when `decision == "APPROVE"` and at least one
recommendation action was `ACCEPT_INCOMING`).

---

## Directory Structure

```
day4/
├── __init__.py
├── README.md
├── models.py                        ← All Pydantic v2 models
├── agent/
│   ├── __init__.py
│   ├── reconciliation_agent.py      ← 4-phase agent class
│   └── tools.py                     ← Async tool functions
├── pipeline/
│   ├── __init__.py
│   ├── event_bus.py                 ← Async pub/sub (asyncio.Queue)
│   ├── ingestor.py                  ← Streaming CSV/JSON parser
│   └── comparator.py               ← Field-level diff engine
├── store/
│   ├── __init__.py
│   ├── master_store.py              ← Security master CRUD (Motor)
│   └── decision_store.py           ← Immutable audit log (Motor)
└── api/
    ├── __init__.py
    └── reconcile.py                 ← FastAPI router at /api/v4
```
