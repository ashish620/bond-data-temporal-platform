# Day 3 — Validation API Endpoint
#
# POST /api/v3/validate/{isin}
#
# Request body:
# {
#   "question": "What is the call schedule for this bond?",
#   "field": "call_schedule"  # optional — specific security master field to validate
# }
#
# Response:
# {
#   "isin": "XS1234567890",
#   "question": "What is the call schedule?",
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
