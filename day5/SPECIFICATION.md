# Day 5 — Immutable Audit Trail & Compliance Layer

> **Purpose:** Transform ad-hoc data overrides (Confluence, spreadsheets) into a compliance-grade, immutable, cryptographically-backed audit system.

---

## The Problem Day 5 Solves

**Current state (pre-Day 5):**
- Day 4 agent recommends override (APPROVE/REJECT)
- Override is applied to security_master
- ❌ No record of *why* it happened
- ❌ No proof it wasn't edited after the fact
- ❌ Operations team documents it in Confluence (editable!)
- ❌ Regulator audit = compliance violation

**Day 5 end-state:**
- Every override decision is **immutably logged**
- Full chain-of-custody: who, what, when, why
- SHA-256 hash prevents tampering
- Optional blockchain backing for crypto-proof
- Regulatory-grade audit trail ready for auditors
- `/api/v5/audit-trail` endpoint for compliance queries

---

## Architecture

```
Day 4: Agent recommends APPROVE/REJECT
       ↓
POST /api/v4/decide
{ finding_id, decision, decided_by, notes }
       ↓
       ├─→ Decision record saved (existing)
       │
       └─→ For each override (ACCEPT_INCOMING):
           ├─→ 1. Update security_master (existing)
           │
           ├─→ 2. Create AuditTrailEntry (NEW — Day 5)
           │       - isin, field_name
           │       - old_value, new_value
           │       - user_id, timestamp, reason
           │
           ├─→ 3. Compute SHA-256 hash (NEW — Day 5)
           │       hash(old+new+user+ts+reason)
           │
           ├─→ 4. Store in audit_trail (NEW — Day 5)
           │       MongoDB append-only collection
           │
           └─→ 5. (Optional) Write hash to blockchain (NEW — Day 5)
                   Async fire-and-forget
                   Polygon testnet or mainnet
```

---

## Release Scope (Day 5)

| Capability | API | Status |
|-----------|-----|--------|
| Immutable audit trail (MongoDB) | `POST /api/v5/audit/*` | ✅ Tier 1 |
| SHA-256 hashing per override | N/A (internal) | ✅ Tier 1 |
| Audit trail retrieval + filtering | `GET /api/v5/audit-trail` | ✅ Tier 1 |
| Blockchain hash backing (testnet) | N/A (async job) | ⚠️ Tier 2 |
| Compliance report generation | `GET /api/v5/compliance-report/{isin}` | ⚠️ Tier 2 |

---

## Data Models (Day 5 Additions)

### `AuditTrailEntry`

```python
from pydantic import BaseModel, Field
from typing import Optional, Any, Literal
from datetime import datetime
from uuid import uuid4

class AuditTrailEntry(BaseModel):
    """
    Immutable record of every data override.
    One entry per field change.
    """
    
    # Identity
    audit_id: str = Field(default_factory=lambda: str(uuid4()))
    isin: str  # Bond identifier
    field_name: str  # e.g., "coupon_rate", "maturity_date"
    
    # The change
    old_value: Any  # from security_master before override
    new_value: Any  # from incoming record (user accepted)
    
    # Attribution
    user_id: str  # who made the decision
    decided_by_user: str  # (redundant for clarity; same as user_id)
    timestamp: datetime  # when the override happened
    
    # Context
    reason: Optional[str] = None  # why they overrode (from /api/v4/decide notes)
    finding_id: str  # link back to ReconciliationFinding
    decision_id: str  # link back to DecisionRecord
    
    # Integrity
    sha256_hash: str  # computed hash of immutable event
    blockchain_tx_hash: Optional[str] = None  # Ethereum/Polygon tx hash (if written)
    blockchain_block: Optional[int] = None  # block number on chain
    
    # Metadata
    source_system: Literal["incoming", "legacy_db", "prospectus"] = "incoming"
    override_reason_category: Optional[str] = None  # e.g., "data_correction", "reconciliation", "system_error"
    
    class Config:
        json_schema_extra = {
            "example": {
                "audit_id": "audit_550e8400e29b41d4a716446655440000",
                "isin": "XS1234567890",
                "field_name": "coupon_rate",
                "old_value": 4.5,
                "new_value": 5.0,
                "user_id": "ashish620",
                "decided_by_user": "ashish620",
                "timestamp": "2026-04-24T10:30:00Z",
                "reason": "Verified with issuer — prospectus was outdated, new rate confirmed in latest pricing supplement",
                "finding_id": "finding_abc123",
                "decision_id": "decision_xyz789",
                "sha256_hash": "a1b2c3d4e5f6...",
                "blockchain_tx_hash": "0x1234567890abcdef...",
                "source_system": "incoming",
                "override_reason_category": "reconciliation"
            }
        }

    def compute_hash(self) -> str:
        """
        Generate SHA-256 hash of the immutable event.
        Hash includes: isin + field + old + new + user + timestamp + reason
        
        This hash serves as cryptographic proof that:
        1. This specific change was recorded
        2. The values weren't tampered with
        3. The user and timestamp are authentic
        """
        import hashlib
        import json
        
        event_data = {
            "isin": self.isin,
            "field_name": self.field_name,
            "old_value": str(self.old_value),
            "new_value": str(self.new_value),
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason or ""
        }
        
        # Deterministic JSON (sorted keys) ensures hash consistency
        event_json = json.dumps(event_data, sort_keys=True)
        return hashlib.sha256(event_json.encode()).hexdigest()
```

### `AuditTrailFilter` (for querying)

```python
class AuditTrailFilter(BaseModel):
    isin: Optional[str] = None
    field_name: Optional[str] = None
    user_id: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    reason_contains: Optional[str] = None  # substring search
    
    limit: int = Field(100, le=1000)  # max 1000 records per query
    offset: int = Field(0, ge=0)
```

### `ComplianceReport` (for auditors)

```python
class ComplianceReport(BaseModel):
    """
    Summary of all overrides for a given ISIN in a date range.
    Perfect for regulatory audits.
    """
    isin: str
    report_generated_at: datetime
    from_date: datetime
    to_date: datetime
    
    total_overrides: int
    overrides_by_field: dict[str, int]  # e.g., {"coupon_rate": 2, "maturity_date": 1}
    overrides_by_user: dict[str, int]  # e.g., {"ashish620": 2, "karen": 1}
    
    entries: list[AuditTrailEntry]
    
    # Integrity check
    hashes_match: bool  # recompute all hashes, verify they match stored hashes
    all_on_blockchain: bool  # are all entries hashed on blockchain?
    blockchain_verification_status: str  # "verified" | "pending" | "not_backed"
```

---

## MongoDB Collections (Day 5 Additions)

### `audit_trail` (append-only)

```python
# MongoDB collection schema (not Python, just structure)
{
  "audit_id": "uuid",
  "isin": "XS1234567890",
  "field_name": "coupon_rate",
  "old_value": 4.5,
  "new_value": 5.0,
  "user_id": "ashish620",
  "timestamp": ISODate("2026-04-24T10:30:00Z"),
  "reason": "...",
  "finding_id": "...",
  "decision_id": "...",
  "sha256_hash": "a1b2c3d4...",
  "blockchain_tx_hash": "0x...",
  "blockchain_block": 18500000,
  "created_at": ISODate("2026-04-24T10:30:05Z")  # when we logged it
}

# Indexes (for fast queries)
{
  "isin": 1,
  "field_name": 1,
  "user_id": 1,
  "timestamp": -1  # descending for recency
}

# CRITICAL: Make this collection append-only
# MongoDB option: use capped collection OR application-level validation
```

### `blockchain_hashes` (optional, for Tier 2)

```python
# Track which hashes have been written to blockchain
{
  "audit_id": "uuid",
  "sha256_hash": "a1b2c3d4...",
  "blockchain_tx_hash": "0x...",
  "blockchain_chain": "polygon_mumbai",  # or "ethereum_mainnet"
  "block_number": 18500000,
  "confirmed_at": ISODate("2026-04-24T10:35:00Z"),
  "status": "confirmed"  # or "pending" | "failed"
}
```

---

## API Endpoints (Day 5)

### `POST /api/v4/decide` (Modified)

**Existing behavior:**
- Saves `DecisionRecord`
- Updates security_master

**New behavior (Day 5):**
- For each override with `recommended_action == "ACCEPT_INCOMING"`:
  - Create `AuditTrailEntry`
  - Compute SHA-256 hash
  - Store in `audit_trail` collection
  - (Async) Write hash to blockchain
  - Return updated `DecisionRecord` with `audit_entries` field

**Response (enhanced):**
```json
{
  "decision_id": "dec789...",
  "finding_id": "finding_abc123...",
  "isin": "XS1234567890",
  "decision": "APPROVE",
  "decided_by": "ashish620",
  "notes": "Verified with issuer",
  "decided_at": "2026-04-24T10:30:00Z",
  
  "fields_updated": [
    {
      "field": "coupon_rate",
      "old": 4.5,
      "new": 5.0,
      "audit_id": "audit_550e8400...",
      "audit_hash": "a1b2c3d4e5f6..."
    }
  ],
  
  "audit_entries": [
    {
      "audit_id": "audit_550e8400...",
      "field_name": "coupon_rate",
      "old_value": 4.5,
      "new_value": 5.0,
      "sha256_hash": "a1b2c3d4...",
      "timestamp": "2026-04-24T10:30:00Z"
    }
  ]
}
```

---

### `GET /api/v5/audit-trail` (New)

**Purpose:** Query the immutable audit trail.

**Query parameters:**
```
isin=XS1234567890
field_name=coupon_rate
user_id=ashish620
from_date=2026-01-01
to_date=2026-04-24
limit=100
offset=0
```

**Response:**
```json
{
  "total": 42,
  "limit": 100,
  "offset": 0,
  "entries": [
    {
      "audit_id": "...",
      "isin": "XS1234567890",
      "field_name": "coupon_rate",
      "old_value": 4.5,
      "new_value": 5.0,
      "user_id": "ashish620",
      "timestamp": "2026-04-24T10:30:00Z",
      "reason": "Verified with issuer",
      "sha256_hash": "a1b2c3d4...",
      "blockchain_tx_hash": "0x1234...",
      "blockchain_confirmed": true
    }
  ]
}
```

---

### `POST /api/v5/audit-trail/verify` (New)

**Purpose:** Verify that an audit entry hasn't been tampered with.

**Request:**
```json
{
  "audit_id": "audit_550e8400..."
}
```

**Response:**
```json
{
  "audit_id": "audit_550e8400...",
  "stored_hash": "a1b2c3d4...",
  "recomputed_hash": "a1b2c3d4...",
  "hashes_match": true,
  "integrity_status": "verified",
  "blockchain_verified": true,
  "blockchain_tx": "0x1234...",
  "message": "✓ This audit entry is cryptographically verified and cannot have been tampered with."
}
```

---

### `GET /api/v5/compliance-report/{isin}` (New)

**Purpose:** Generate a compliance report for auditors.

**Query parameters:**
```
from_date=2026-01-01
to_date=2026-04-24
include_blockchain_verification=true
```

**Response:**
```json
{
  "isin": "XS1234567890",
  "report_generated_at": "2026-04-24T15:00:00Z",
  "from_date": "2026-01-01",
  "to_date": "2026-04-24",
  
  "total_overrides": 5,
  "overrides_by_field": {
    "coupon_rate": 2,
    "maturity_date": 1,
    "call_schedule": 2
  },
  "overrides_by_user": {
    "ashish620": 4,
    "karen": 1
  },
  
  "entries": [...],
  
  "integrity_check": {
    "all_hashes_valid": true,
    "all_on_blockchain": true,
    "blockchain_chain": "polygon_mumbai",
    "verification_timestamp": "2026-04-24T15:00:05Z"
  },
  
  "summary": "5 data overrides recorded for XS1234567890 between 2026-01-01 and 2026-04-24. All entries cryptographically verified and backed on blockchain."
}
```

---

## Implementation Plan

### Phase 1: Core Audit Trail (Tier 1)
**Effort:** 4-6 hours | **Complexity:** Medium | **Dependencies:** Day 4 exists

```
1. Create day5/models.py
   - AuditTrailEntry
   - AuditTrailFilter
   - ComplianceReport

2. Create day5/store/audit_store.py
   - save_audit_trail_entry()
   - get_audit_trail()
   - verify_entry_integrity()
   - generate_compliance_report()

3. Create day5/api/audit.py
   - GET /api/v5/audit-trail
   - POST /api/v5/audit-trail/verify
   - GET /api/v5/compliance-report/{isin}

4. Modify day4/store/decision_store.py
   - After APPROVE decision, call audit_store.save_audit_trail_entry()

5. Create tests/test_day5_audit.py
   - Test hash consistency
   - Test immutability (can't modify entries)
   - Test compliance report generation
```

### Phase 2: Blockchain Backing (Tier 2)
**Effort:** 3-4 hours | **Complexity:** Medium | **Dependencies:** Tier 1 complete

```
1. Create day5/blockchain/polygon_writer.py
   - Write hash to Polygon smart contract
   - Handle async retries
   - Log transaction hash

2. Create day5/blockchain/smart_contract.sol
   - Simple Solidity contract to record hashes
   - Emit events (on-chain logging)

3. Create day5/api/blockchain.py
   - GET /api/v5/blockchain-status/{audit_id}
   - Show tx hash, block, confirmation status

4. Add .env variables
   - POLYGON_RPC_URL
   - AUDIT_CONTRACT_ADDRESS
   - BLOCKCHAIN_ENABLED (feature flag)

5. Add to requirements.txt
   - web3>=6.0.0
```

### Phase 3: Compliance Dashboard (Tier 3 — future)
```
- React frontend component
- Query audit trail with filters
- Display compliance reports
- Show blockchain verification status
```

---

## Why Day 5 is Distinct from Day 4

| Aspect | Day 4 | Day 5 |
|--------|-------|-------|
| **Purpose** | AI-driven reconciliation | Immutable audit trail |
| **Problem** | How to detect & recommend fixes | How to prove fixes were legitimate |
| **Output** | `ReconciliationFinding` + `DecisionRecord` | `AuditTrailEntry` + compliance-grade proof |
| **Regulatory** | Aids detection | Proves integrity (SEC Rule 17a-4) |
| **Audience** | Operations team | Auditors + Regulators |
| **Storage** | MongoDB | MongoDB + Blockchain (optional) |

---

## Success Criteria (Day 5 Complete)

✅ Every override is immutably logged with user/timestamp/reason  
✅ SHA-256 hash prevents tampering detection  
✅ MongoDB audit_trail is append-only (no edits/deletes possible)  
✅ `/api/v5/audit-trail` endpoint allows filtering by ISIN/user/date  
✅ `/api/v5/compliance-report` generates auditor-ready reports  
✅ Hashes can be verified with `/api/v5/audit-trail/verify`  
✅ (Optional) Hashes written to blockchain for crypto-proof  
✅ All Day 5 endpoints tested + documented  
✅ Regulatory defensibility: "Here's proof this override was intentional and immutable"

---

## Files to Create/Modify

```
day5/
├── __init__.py
├── README.md  ← Link to AUDIT_TRAIL_JUSTIFICATION.md
├── models.py  ← AuditTrailEntry, AuditTrailFilter, ComplianceReport
├── store/
│   ├── __init__.py
│   ├── audit_store.py  ← Main audit trail logic
│   └── blockchain_store.py  ← (Tier 2) Blockchain writing
├── blockchain/
│   ├── __init__.py
│   ├── polygon_writer.py  ← (Tier 2)
│   ├── contract.sol  ← (Tier 2)
│   └── abi.json  ← (Tier 2)
├── api/
│   ├── __init__.py
│   ├── audit.py  ← /api/v5 endpoints
│   └── blockchain.py  ← (Tier 2) blockchain status
└── tests/
    ├── __init__.py
    ├── test_audit_store.py
    ├── test_audit_hashing.py
    ├── test_compliance_report.py
    └── test_blockchain_integration.py

Modify:
├── day4/store/decision_store.py
│   └── Call audit_store after APPROVE decisions
└── day4/api/reconcile.py
    └── Return audit_entries in /api/v4/decide response
```

---

## Environment Variables (Day 5)

```env
# MongoDB (existing)
MONGODB_CURRENT_URL=mongodb://localhost:27018
MONGODB_LEGACY_URL=mongodb://localhost:27017

# Day 5 Audit Trail
AUDIT_TRAIL_ENABLED=true
AUDIT_TRAIL_APPEND_ONLY=true  # enforce at application level

# Day 5 Blockchain (Tier 2)
BLOCKCHAIN_ENABLED=true
BLOCKCHAIN_CHAIN=polygon_mumbai  # or ethereum_goerli, ethereum_mainnet
POLYGON_RPC_URL=https://mumbai.polygonscan.com/...
AUDIT_CONTRACT_ADDRESS=0x...
BLOCKCHAIN_PRIVATE_KEY=0x...
BLOCKCHAIN_WRITE_TIMEOUT=30
BLOCKCHAIN_RETRY_COUNT=3
```

---

## Timeline

**Day 5 Tier 1 (Immutable audit trail + hashing):** 1 day  
**Day 5 Tier 2 (Blockchain backing):** +1 day  
**Day 5 Tier 3 (Compliance dashboard):** +2-3 days  

---

## Success Story (Post-Day 5)

```
Scenario: SEC auditor asks for override history for XS1234567890

BEFORE (Confluence):
  Auditor: "Show me proof no one edited this"
  You: "Well... Confluence can be edited by anyone..."
  Auditor: "Compliance violation. $500K fine."

AFTER (Day 5):
  Auditor: "Show me override history"
  You: "Here's /api/v5/compliance-report/XS1234567890"
  → Shows 5 overrides, all user-attributed, timestamped, with reasons
  → Shows SHA-256 hashes prove data integrity
  → Shows blockchain transaction hashes proving immutability
  Auditor: "Perfect. ✓ Compliant."
```

---

## Next Steps

Ready to build? I can start with:

1. **Tier 1 implementation** (MongoDB audit trail + SHA-256 hashing)
   - `day5/models.py`
   - `day5/store/audit_store.py`
   - `day5/api/audit.py`
   - Tests

2. **Integration with Day 4**
   - Modify `/api/v4/decide` to create audit entries

3. **Documentation**
   - `day5/README.md`
   - API docs

**Shall I begin?**
