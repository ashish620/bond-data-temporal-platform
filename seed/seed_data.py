"""
Seed script — populates both MongoDB containers with realistic bond snapshot data.

Run via docker-compose seed service or directly:
    python seed/seed_data.py

Legacy DB (port 27017): bond snapshots before 2026-01-01
Current DB (port 27018): bond snapshots from 2026-01-01 onwards
"""

import asyncio
import os
from datetime import date, timedelta

import motor.motor_asyncio

LEGACY_MONGO_URI = os.getenv("LEGACY_MONGO_URI", "mongodb://localhost:27017")
CURRENT_MONGO_URI = os.getenv("CURRENT_MONGO_URI", "mongodb://localhost:27018")

LEGACY_DB_NAME = os.getenv("LEGACY_DB_NAME", "legacy_bonds")
CURRENT_DB_NAME = os.getenv("CURRENT_DB_NAME", "current_bonds")

BONDS_COLLECTION = "bond_snapshots"

# ---------------------------------------------------------------------------
# Sample bond data — two ISINs with snapshots in both DBs
# ---------------------------------------------------------------------------

LEGACY_SNAPSHOTS = [
    {
        "isin": "XS1234567890",
        "snapshot_date": "2025-01-15",
        "issuer_name": "Acme Corp",
        "maturity_date": "2030-01-15",
        "coupon_rate": 3.5,
        "currency": "USD",
        "face_value": 1000.0,
    },
    {
        "isin": "XS1234567890",
        "snapshot_date": "2025-04-15",
        "issuer_name": "Acme Corp",
        "maturity_date": "2030-01-15",
        "coupon_rate": 3.5,
        "currency": "USD",
        "face_value": 1000.0,
    },
    {
        "isin": "XS1234567890",
        "snapshot_date": "2025-07-15",
        "issuer_name": "Acme Corp",
        "maturity_date": "2030-01-15",
        "coupon_rate": 3.5,
        "currency": "USD",
        "face_value": 1000.0,
    },
    {
        "isin": "XS9876543210",
        "snapshot_date": "2025-03-01",
        "issuer_name": "Globex Holdings",
        "maturity_date": "2028-03-01",
        "coupon_rate": 4.25,
        "currency": "EUR",
        "face_value": 500.0,
    },
    {
        "isin": "XS9876543210",
        "snapshot_date": "2025-09-01",
        "issuer_name": "Globex Holdings",
        "maturity_date": "2028-03-01",
        "coupon_rate": 4.25,
        "currency": "EUR",
        "face_value": 500.0,
    },
    {
        "isin": "XS9876543210",
        "snapshot_date": "2025-12-01",
        "issuer_name": "Globex Holdings",
        "maturity_date": "2028-03-01",
        "coupon_rate": 4.25,
        "currency": "EUR",
        "face_value": 500.0,
    },
]

CURRENT_SNAPSHOTS = [
    {
        "isin": "XS1234567890",
        "snapshot_date": "2026-01-15",
        "issuer_name": "Acme Corp",
        "maturity_date": "2030-01-15",
        "coupon_rate": 3.5,
        "currency": "USD",
        "face_value": 1000.0,
    },
    {
        "isin": "XS1234567890",
        "snapshot_date": "2026-04-15",
        "issuer_name": "Acme Corp",
        "maturity_date": "2030-01-15",
        "coupon_rate": 3.5,
        "currency": "USD",
        "face_value": 1000.0,
    },
    {
        "isin": "XS1234567890",
        "snapshot_date": "2026-07-15",
        "issuer_name": "Acme Corp",
        "maturity_date": "2030-01-15",
        "coupon_rate": 3.5,
        "currency": "USD",
        "face_value": 1000.0,
    },
    {
        "isin": "XS9876543210",
        "snapshot_date": "2026-03-01",
        "issuer_name": "Globex Holdings",
        "maturity_date": "2028-03-01",
        "coupon_rate": 4.25,
        "currency": "EUR",
        "face_value": 500.0,
    },
    {
        "isin": "XS9876543210",
        "snapshot_date": "2026-06-01",
        "issuer_name": "Globex Holdings",
        "maturity_date": "2028-03-01",
        "coupon_rate": 4.25,
        "currency": "EUR",
        "face_value": 500.0,
    },
    {
        "isin": "XS9876543210",
        "snapshot_date": "2026-09-01",
        "issuer_name": "Globex Holdings",
        "maturity_date": "2028-03-01",
        "coupon_rate": 4.25,
        "currency": "EUR",
        "face_value": 500.0,
    },
]


async def seed_legacy() -> None:
    client = motor.motor_asyncio.AsyncIOMotorClient(LEGACY_MONGO_URI)
    col = client[LEGACY_DB_NAME][BONDS_COLLECTION]
    await col.drop()
    await col.insert_many(LEGACY_SNAPSHOTS)
    await col.create_index([("isin", 1), ("snapshot_date", 1)])
    print(f"[seed] Legacy DB: inserted {len(LEGACY_SNAPSHOTS)} snapshots")
    client.close()


async def seed_current() -> None:
    client = motor.motor_asyncio.AsyncIOMotorClient(CURRENT_MONGO_URI)
    col = client[CURRENT_DB_NAME][BONDS_COLLECTION]
    await col.drop()
    await col.insert_many(CURRENT_SNAPSHOTS)
    await col.create_index([("isin", 1), ("snapshot_date", 1)])
    print(f"[seed] Current DB: inserted {len(CURRENT_SNAPSHOTS)} snapshots")
    client.close()


async def main() -> None:
    await asyncio.gather(seed_legacy(), seed_current())
    print("[seed] Done.")


if __name__ == "__main__":
    asyncio.run(main())
