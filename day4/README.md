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

### Where Intelligence Is Applied

The system uses LLM reasoning at **four precise points** — not indiscriminately. This is intentional to keep costs bounded and latency predictable.

| Phase | Where LLM Is Used | What It Does |
|---|---|---|
| **Phase 1 — Plan** | `gpt-4o-mini` (JSON mode) | Given the mismatched fields and ISIN, decides which data sources are worth querying. Avoids fetching all three sources blindly — e.g. skips prospectus lookup for `face_value` mismatches where the document is unlikely to resolve the dispute. |
| **Phase 2 — Execute** | `text-embedding-ada-002` | Embeds per-field natural language questions for prospectus vector search. Only called for fields the Plan phase flagged as worth checking in the prospectus. |
| **Phase 3 — Validate** | `gpt-4o-mini` (JSON mode) | For each mismatched field, interprets all four data points — incoming value, master value, historical legacy snapshots, and prospectus answer — and decides which source is most likely correct and why. This is where mismatch interpretation happens: it doesn't just flag differences, it reasons about which side is right. |
| **Phase 4 — Resolve** | `gpt-4o-mini` | Synthesises all field-level assessments into a human-readable summary explaining the overall situation for the analyst reviewing the finding. |

Key design choices:
- **Interpretation, not just detection**: The comparator (pure Python, no LLM) detects mismatches. The agent interprets them — deciding which source to trust, what the likely cause is, and what action to recommend.
- **Reasoning is explicit**: Each `AgentRecommendation` includes a `reasoning` field containing the agent's natural-language explanation — the analyst sees exactly why the agent recommended `KEEP_MASTER` or `ACCEPT_INCOMING`, not just the outcome.
- **Source trust hierarchy**: The agent considers prospectus > historical consistency > current master > incoming value, but this hierarchy is reasoned about per-field — not hard-coded. A coupon rate that differs from the prospectus by 5bps will be flagged differently to an issuer name that differs only in capitalisation.

### Confidence Scoring

Every `AgentRecommendation` carries a `confidence` field: `"high"`, `"medium"`, or `"low"`. This is determined differently at each layer:

**RAG layer (Phase 2 — Prospectus lookup):**
Confidence is derived from the mean cosine distance of retrieved ChromaDB chunks:

| Mean Distance | Confidence |
|---|---|
| < 0.3 | `high` — prospectus excerpt is a strong match for the question |
| 0.3 – 0.6 | `medium` — relevant context found but not an exact match |
| > 0.6 | `low` — chunks retrieved are loosely related; answer may be unreliable |

**Agent layer (Phase 3 — Validate):**
The `assess_field_consistency()` tool asks `gpt-4o-mini` to also return a confidence label alongside its recommendation. Factors that lower confidence:
- Prospectus lookup returned `"Not found in prospectus"` — only two sources to compare
- Historical legacy values are inconsistent across snapshots (multiple conflicting values in DB)
- The two values differ in a way that could be a genuine business change (e.g. refinancing) rather than a data error

**How confidence affects the workflow:**
- `high` confidence → agent recommends `ACCEPT_INCOMING` or `KEEP_MASTER` definitively
- `medium` confidence → agent may still make a recommendation but flags it for closer review
- `low` confidence → agent always recommends `MANUAL_REVIEW` regardless of which value looks more plausible

### Failure Handling & Graceful Degradation

The agent is designed to never crash the pipeline. Each failure mode is handled explicitly:

| Failure Mode | Behaviour |
|---|---|
| **No prospectus ingested for ISIN** | `query_prospectus()` catches `ValueError` from `RAGQueryEngine` and returns `{"answer": "Not found in prospectus", "confidence": "low"}`. Agent continues with only DB sources. |
| **Legacy/Current DB returns no snapshots** | Agent proceeds with empty historical context. Phase 3 assess call receives an empty list for `legacy_values`. Confidence degrades to `low` or `medium`. |
| **LLM call fails (OpenAI timeout/rate limit)** | Each LLM call in Phase 1, 3, 4 is wrapped in try/except. On failure the agent returns a `MANUAL_REVIEW` recommendation with `confidence: "low"` and a `reasoning` explaining the failure. The finding is still saved to `DecisionStore` — the analyst sees the raw mismatch data even if the agent couldn't reason about it. |
| **Master record not found** | If `MasterStore.get()` returns `None` (ISIN+date not in security master), the record is treated as a new record — no mismatch is possible, no event is published. |
| **Malformed CSV/JSON row** | `FileIngestor` skips malformed rows and logs a warning. Processing continues for valid rows. |
| **Event bus subscriber crash** | Wrapped in try/except; failure of one agent instance does not affect other concurrent instances. |

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
