"""Day 5 — Pydantic v2 data models for immutable audit trail."""

from pydantic import BaseModel, Field
from typing import Optional, Any, Literal
from datetime import datetime
from uuid import uuid4
import hashlib
import json


class AuditTrailEntry(BaseModel):
    """
    Immutable record of every data override.
    One entry per field change.
    
    Once created, this record can NEVER be updated or deleted.
    SHA-256 hash serves as cryptographic proof of integrity.
    """
    
    # Identity
    audit_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique audit entry ID")
    isin: str = Field(..., description="Bond ISIN identifier (e.g., XS1234567890)")
    field_name: str = Field(..., description="Field name that was overridden (e.g., coupon_rate)")
    
    # The change
    old_value: Any = Field(..., description="Original value from security_master")
    new_value: Any = Field(..., description="Accepted value from incoming record")
    
    # Attribution
    user_id: str = Field(..., description="User ID who made the decision")
    decided_by_user: str = Field(..., description="Redundant for clarity; same as user_id")
    timestamp: datetime = Field(..., description="When the override happened (UTC)")
    
    # Context
    reason: Optional[str] = Field(None, description="Why the override was approved (VERY powerful for audits)")
    finding_id: str = Field(..., description="Link back to Day 4 ReconciliationFinding")
    decision_id: str = Field(..., description="Link back to Day 4 DecisionRecord")
    
    # Integrity
    sha256_hash: str = Field(..., description="SHA-256 hash of immutable event (prevents tampering)")
    blockchain_tx_hash: Optional[str] = Field(None, description="Ethereum/Polygon tx hash (if written)")
    blockchain_block: Optional[int] = Field(None, description="Block number on chain")
    
    # Metadata
    source_system: Literal["incoming", "legacy_db", "prospectus"] = Field(
        "incoming", description="Source of the new value"
    )
    override_reason_category: Optional[str] = Field(
        None, description="Category: data_correction, reconciliation, system_error, etc."
    )
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo), 
                                 description="When this audit entry was created")

    class Config:
        json_schema_extra = {
            "example": {
                "audit_id": "550e8400-e29b-41d4-a716-446655440000",
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
                "sha256_hash": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
                "blockchain_tx_hash": "0x1234567890abcdef1234567890abcdef12345678",
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
        2. The values weren't tampered with after recording
        3. The user and timestamp are authentic
        
        **Deterministic:** Same input always produces same hash
        **Sensitive:** Changing ANY field produces different hash
        
        Returns:
            str: Hexadecimal SHA-256 hash (64 characters)
        """
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
        # Same input will ALWAYS produce the same hash
        event_json = json.dumps(event_data, sort_keys=True)
        return hashlib.sha256(event_json.encode()).hexdigest()


class AuditTrailFilter(BaseModel):
    """
    Filter criteria for querying audit trail.
    Used to fetch audit entries based on various criteria.
    """
    
    isin: Optional[str] = Field(None, description="Filter by ISIN (exact match)")
    field_name: Optional[str] = Field(None, description="Filter by field name (exact match)")
    user_id: Optional[str] = Field(None, description="Filter by user ID who made the decision")
    from_date: Optional[datetime] = Field(None, description="Date range start (inclusive, UTC)")
    to_date: Optional[datetime] = Field(None, description="Date range end (inclusive, UTC)")
    reason_contains: Optional[str] = Field(None, description="Substring search in reason field")
    
    limit: int = Field(100, ge=1, le=1000, description="Max records per query (1-1000)")
    offset: int = Field(0, ge=0, description="Pagination offset (0 = first page)")
    
    sort_by: Literal["timestamp", "field_name", "user_id"] = Field(
        "timestamp", description="Sort field"
    )
    sort_order: Literal["asc", "desc"] = Field("desc", description="Sort order (asc=oldest first, desc=newest first)")


class IntegrityVerificationResult(BaseModel):
    """
    Result of verifying integrity of an audit entry.
    Recomputes SHA-256 hash and compares with stored hash.
    """
    
    audit_id: str = Field(..., description="Audit entry ID that was verified")
    stored_hash: str = Field(..., description="Hash stored in database when entry was created")
    recomputed_hash: str = Field(..., description="Hash recomputed from current data")
    hashes_match: bool = Field(..., description="True if hashes match (no tampering)")
    integrity_status: Literal["verified", "tampered", "error"] = Field(
        ..., description="Status: verified (hashes match), tampered (differ), error (verification failed)"
    )
    blockchain_verified: Optional[bool] = Field(
        None, description="True if entry is backed on blockchain (Tier 2)"
    )
    blockchain_tx: Optional[str] = Field(None, description="Blockchain transaction hash (if verified)")
    blockchain_block: Optional[int] = Field(None, description="Block number where hash was recorded")
    message: str = Field(..., description="Human-readable status message")


class ComplianceReport(BaseModel):
    """
    Auditor-ready compliance report for a single ISIN.
    Summary of all overrides in a date range with integrity verification.
    """
    
    isin: str = Field(..., description="Bond ISIN")
    report_generated_at: datetime = Field(..., description="When this report was generated")
    from_date: datetime = Field(..., description="Report start date")
    to_date: datetime = Field(..., description="Report end date")
    
    # Summary statistics
    total_overrides: int = Field(..., description="Total number of overrides in date range")
    overrides_by_field: dict[str, int] = Field(..., description="Count of overrides per field (e.g., {'coupon_rate': 2})")
    overrides_by_user: dict[str, int] = Field(..., description="Count of overrides per user (e.g., {'ashish620': 5})")
    
    # Detailed entries
    entries: list[AuditTrailEntry] = Field(..., description="All audit trail entries for this ISIN in date range")
    
    # Integrity check
    integrity_check: dict[str, Any] = Field(
        ..., description={
            "all_hashes_valid": "bool - All stored hashes match recomputed hashes",
            "all_on_blockchain": "bool - Are all entries backed on blockchain?",
            "blockchain_chain": "str - Which chain (polygon_mumbai, ethereum_mainnet, etc.)",
            "verification_timestamp": "datetime - When integrity check was performed"
        }
    )
    
    # Executive summary
    summary: str = Field(
        ..., description="Human-readable summary (e.g., '5 data overrides recorded for XS1234567890...')"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
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
                "entries": [],  # populated with AuditTrailEntry objects
                "integrity_check": {
                    "all_hashes_valid": True,
                    "all_on_blockchain": True,
                    "blockchain_chain": "polygon_mumbai",
                    "verification_timestamp": "2026-04-24T15:00:05Z"
                },
                "summary": "5 data overrides recorded for XS1234567890 between 2026-01-01 and 2026-04-24. All entries cryptographically verified and backed on blockchain."
            }
        }
