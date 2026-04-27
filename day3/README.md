# Day 3 — NLP + RAG: Prospectus-Grounded Security Master Validation

This is the third and most advanced query mode — the same natural language interface as Day 2 (`POST /api/v1/query`) but now grounded in actual bond prospectus PDFs. Instead of LLM answers from parametric knowledge, every answer is retrieved from and cited to the original bond documents stored in a ChromaDB vector store.

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
Natural language query (e.g. "What is the call schedule for XS1234567890?")
        ↓
LLM extracts ISIN + question intent
        ↓
Bond Prospectus PDFs (per ISIN)
        ↓
PDF Ingestion Pipeline         ← day3/ingestion/pdf_ingester.py
        ↓
Chunking + Embedding           ← OpenAI text-embedding-ada-002
(chunk_size=1000, overlap=200)
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
