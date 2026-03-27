"""
Configuration for Bond Data Intelligence Platform.

CUTOFF_DATE is the single source of truth for the time boundary between
Legacy MongoDB (pre-2026) and Current MongoDB (from 2026 onwards).
"""

import os
from datetime import date

from dotenv import load_dotenv

load_dotenv()

# Single source of truth — all routing logic references this constant
CUTOFF_DATE = date(2026, 1, 1)

# MongoDB connection strings loaded from environment variables
LEGACY_MONGO_URI = os.getenv("LEGACY_MONGO_URI", "mongodb://localhost:27017")
CURRENT_MONGO_URI = os.getenv("CURRENT_MONGO_URI", "mongodb://localhost:27018")

LEGACY_DB_NAME = os.getenv("LEGACY_DB_NAME", "legacy_bonds")
CURRENT_DB_NAME = os.getenv("CURRENT_DB_NAME", "current_bonds")

BONDS_COLLECTION = "bond_snapshots"
