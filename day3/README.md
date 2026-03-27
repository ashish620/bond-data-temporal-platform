# Day 3 — Prospectus-Grounded Security Master Validation

## The Problem

When data disputes arise in security master — particularly around call schedules, put
schedules, and conversion schedules — the final word has always been the original bond
prospectus or certificate. In practice, quants with access to these documents would
manually read through them to resolve mismatches.

The entire resolution workflow was manual:

```
Data mismatch flagged in security master
        ↓
Quant with prospectus access manually reads through PDF
        ↓
Finds correct call/put/conversion schedule (often buried deep in document)
        ↓
That becomes source of truth for the data fix
```

Nobody had made those documents machine-queryable. This component eliminates the
manual lookup entirely.

---

## Architecture

```
Bond Prospectus PDFs (per ISIN)
        ↓
PDF Ingestion Pipeline         ← day3/ingestion/pdf_ingester.py
        ↓
Chunking + Embedding           ← OpenAI text-embedding-ada-002
(chunk_size=1000, overlap=200)    or sentence-transformers/all-MiniLM-L6-v2
        ↓
Vector Store (ChromaDB)        ← day3/ingestion/document_store.py
(keyed by ISIN + document_type)
        ↓
RAG Query Engine               ← day3/rag/query_engine.py
        ↓
POST /api/v3/validate/{isin}   ← day3/api/validate.py
        ↓
Grounded answer + prospectus citation + mismatch flag
```

---

## Document Types Supported

| Document | What it contains |
|----------|-----------------|
| Prospectus / Offering Circular | Full bond terms — call/put/conversion schedules, covenants |
| Final Terms | Specific economic terms for that ISIN |
| Pricing Supplement | Amendments to base prospectus |
| Corporate Action Notices | Restructurings, early redemptions, consent solicitations |

---

## Planned API Endpoint

### `POST /api/v3/validate/{isin}`

**Request body:**
```json
{
  "question": "What is the call schedule for this bond?",
  "field": "call_schedule"
}
```

**Response:**
```json
{
  "isin": "XS1234567890",
  "question": "What is the call schedule?",
  "answer": "Per the Offering Circular dated 12 March 2019 (page 147)...",
  "sources": [
    {
      "page": 147,
      "document": "Offering_Circular_2019.pdf",
      "excerpt": "..."
    }
  ],
  "mismatch_detected": true,
  "security_master_value": "par flat",
  "prospectus_value": "par + 0.5% call premium",
  "recommendation": "Review call premium field in security master for ISIN XS1234567890"
}
```

---

## Coupon Validation — Fixed and Floating Rate Bonds

Coupon data in security master is a frequent source of disputes, particularly for floating rate bonds where the coupon formula involves multiple components sourced from the prospectus.

### Fixed Rate Bonds
The prospectus states coupon rate, frequency, and day count convention explicitly.
RAG validates all three against security master — a common mismatch is day count convention
(e.g. security master has Act/365 but prospectus states 30/360).

### Floating Rate Bonds
The coupon formula is defined in natural language in the prospectus:
> "The Notes will bear interest at a rate equal to 3-month EURIBOR plus a margin
> of 1.25 per cent. per annum, reset quarterly, calculated on an Act/360 basis,
> subject to a minimum rate of zero per cent. per annum."

RAG extracts:
- Reference rate: 3M EURIBOR
- Spread: 125bps
- Reset frequency: quarterly
- Day count: Act/360
- Floor: 0%
- Cap: none

Each component is then validated against the corresponding security master field.
A mismatch in spread of even 5bps can have significant P&L impact at scale.

### Validatable Fields
| Field | Fixed | Floating | Why it matters |
|-------|-------|----------|----------------|
| coupon_rate | ✅ | ❌ | Core economic term |
| coupon_formula | ❌ | ✅ | Full floating rate definition |
| reference_rate | ❌ | ✅ | SOFR vs EURIBOR mix-up common |
| spread | ❌ | ✅ | 5bps error = material at scale |
| day_count_convention | ✅ | ✅ | Affects accrual calculation |
| coupon_frequency | ✅ | ✅ | Semi-annual vs quarterly |
| reset_frequency | ❌ | ✅ | Monthly vs quarterly |
| coupon_floor | ❌ | ✅ | 0% floor important post-negative rates |
| coupon_cap | ❌ | ✅ | Caps affect structured products |
| call_schedule | ✅ | ✅ | Call dates + premium |
| put_schedule | ✅ | ✅ | Put dates + price |
| conversion_schedule | ✅ | ✅ | Convertible bond terms |

---

## Component Structure

```
day3/
├── ingestion/
│   ├── __init__.py
│   ├── pdf_ingester.py      — PDF loading, chunking, embedding, ChromaDB storage
│   └── document_store.py    — Abstraction layer over ChromaDB
├── rag/
│   ├── __init__.py
│   └── query_engine.py      — RAG engine: embed query → retrieve chunks → LLM answer
├── api/
│   ├── __init__.py
│   └── validate.py          — FastAPI endpoint: POST /api/v3/validate/{isin}
├── requirements_day3.txt    — Additional dependencies for Day 3
└── README.md                — This file
```

---

## Dependencies

Install on top of the main `requirements.txt`:

```
langchain>=0.1.0
langchain-openai>=0.0.5
chromadb>=0.4.0
pypdf>=3.0.0
sentence-transformers>=2.2.0
openai>=1.0.0
```

See `requirements_day3.txt` for the pinned list.

---

## Environment Variables (Day 3 additions)

```
OPENAI_API_KEY=sk-...          # Required if using OpenAI embeddings / GPT-4
CHROMA_PERSIST_DIR=./chroma_db # Local ChromaDB storage path
EMBEDDING_MODEL=openai         # "openai" or "sentence-transformers"
```
