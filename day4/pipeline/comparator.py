"""
Day 4 — Field-level comparator between an incoming record and the security master.

Compares the fields defined in COMPARABLE_FIELDS and returns one FieldMismatch
per differing field.  Uses tolerances and normalisation appropriate for each
data type.
"""

from app.models import BondSnapshot
from day4.models import FieldMismatch, IncomingRecord

# Fields compared between incoming record and security master
COMPARABLE_FIELDS = [
    "issuer_name",
    "maturity_date",
    "coupon_rate",
    "currency",
    "face_value",
]

_FLOAT_TOLERANCE = 0.0001


class Comparator:
    """
    Compares an IncomingRecord against a BondSnapshot (security master entry).

    Returns a list of FieldMismatch objects, one per differing field.
    An empty list means the record is clean.
    """

    def compare(self, incoming: IncomingRecord, master: BondSnapshot) -> list[FieldMismatch]:
        """
        Perform field-level comparison.

        Rules:
        - floats:   tolerance of 0.0001 (absolute difference)
        - dates:    compared as date objects
        - strings:  case-insensitive strip comparison

        Returns:
            list[FieldMismatch] — empty list if all comparable fields match.
        """
        mismatches: list[FieldMismatch] = []

        for field in COMPARABLE_FIELDS:
            incoming_val = getattr(incoming, field)
            master_val = getattr(master, field)

            if not self._fields_match(field, incoming_val, master_val):
                mismatches.append(
                    FieldMismatch(
                        field=field,
                        incoming_value=incoming_val,
                        master_value=master_val,
                    )
                )

        return mismatches

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fields_match(field: str, incoming_val: object, master_val: object) -> bool:
        """Return True if the two values are considered equal for the given field."""
        if isinstance(incoming_val, float) and isinstance(master_val, float):
            return abs(incoming_val - master_val) <= _FLOAT_TOLERANCE

        if isinstance(incoming_val, str) and isinstance(master_val, str):
            return incoming_val.strip().lower() == master_val.strip().lower()

        # date objects and everything else — direct equality
        return incoming_val == master_val
