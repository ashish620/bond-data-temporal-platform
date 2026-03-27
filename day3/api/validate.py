# Day 3 — Validation API Endpoint
#
# POST /api/v3/validate/{isin}
#
# Request body:
# {
#   "question": "What is the coupon rate and day count convention for ISIN XS1234567890?",
#   "field": "coupon_rate"  # optional — specific security master field to validate
# }
#
# ValidatableField covers all real-world prospectus lookup use cases:
#
# from typing import Literal
#
# ValidatableField = Literal[
#     # Coupon fields — fixed rate
#     "coupon_rate",
#     "coupon_type",               # fixed / floating / zero
#     "day_count_convention",      # Act/360, Act/365, 30/360 etc.
#     "coupon_frequency",          # annual, semi-annual, quarterly, monthly
#     # Coupon fields — floating/variable rate
#     "coupon_formula",            # e.g. 3M EURIBOR + 125bps
#     "reference_rate",            # SOFR, EURIBOR, LIBOR etc.
#     "spread",                    # bps over reference rate
#     "reset_frequency",           # how often coupon resets
#     "coupon_floor",              # minimum coupon e.g. 0%
#     "coupon_cap",                # maximum coupon e.g. 5%
#     # Schedule fields
#     "call_schedule",
#     "put_schedule",
#     "conversion_schedule",
# ]
#
# Response examples:
#
# Fixed rate coupon:
# {
#   "isin": "XS1234567890",
#   "question": "What is the coupon rate and day count convention for ISIN XS1234567890?",
#   "answer": "Per Final Terms (page 12): coupon rate is 3.875% per annum,
#              paid semi-annually, on a 30/360 basis.
#              Security master shows 3.850% — potential mismatch flagged.",
#   "sources": [{"page": 12, "document": "Final_Terms_2019.pdf", "excerpt": "..."}],
#   "mismatch_detected": true,
#   "security_master_value": "3.850%",
#   "prospectus_value": "3.875%",
#   "recommendation": "Review coupon_rate field in security master for ISIN XS1234567890"
# }
#
# Floating rate coupon:
# {
#   "isin": "XS9876543210",
#   "question": "What is the coupon formula for ISIN XS9876543210?",
#   "answer": "Per Offering Circular (page 34): 3M EURIBOR + 125bps,
#              reset quarterly, Act/360 day count, floor at 0%, no cap.
#              Security master shows spread of 120bps — potential mismatch flagged.",
#   "sources": [{"page": 34, "document": "Offering_Circular_2021.pdf", "excerpt": "..."}],
#   "mismatch_detected": true,
#   "security_master_value": "spread: 120bps",
#   "prospectus_value": "spread: 125bps",
#   "recommendation": "Review spread field in security master for ISIN XS9876543210"
# }
#
# Call schedule:
# {
#   "isin": "XS1234567890",
#   "question": "What is the call schedule for this bond?",
#   "answer": "Per the Offering Circular dated 12 March 2019 (page 147)...",
#   "sources": [{"page": 147, "document": "Offering_Circular_2019.pdf", "excerpt": "..."}],
#   "mismatch_detected": true,
#   "security_master_value": "par flat",
#   "prospectus_value": "par + 0.5% call premium",
#   "recommendation": "Review call premium field in security master for ISIN XS1234567890"
# }
#
# TODO Day 3: Implement validate endpoint
# TODO Day 3: Wire up ProspectusQueryEngine
# TODO Day 3: Wire up mismatch detection against security master MongoDB
