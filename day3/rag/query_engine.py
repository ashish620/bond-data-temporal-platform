# Day 3 — RAG Query Engine
#
# Purpose: Given an ISIN and a natural language question, retrieve relevant
# prospectus chunks from ChromaDB and generate a grounded answer using an LLM.
#
# Flow:
#   1. Accept isin + question (e.g. "What is the call schedule?")
#   2. Embed the question
#   3. Retrieve top-k most similar chunks from ChromaDB (filtered by isin)
#   4. Construct prompt:
#      "Based on the following excerpts from the bond prospectus for {isin},
#       answer the question: {question}
#
#       Prospectus excerpts:
#       {retrieved_chunks}
#
#       If the answer is not found in the excerpts, say so explicitly.
#       Always cite the source page number."
#   5. Send to LLM (OpenAI GPT-4 or open source alternative)
#   6. Return answer + source citations + page references
#
# Mismatch detection (the key feature):
#   After generating the answer, compare against current security master value
#   from MongoDB. If they differ → flag as potential data issue.
#
# TODO Day 3: Implement ProspectusQueryEngine class
# TODO Day 3: Implement mismatch detection against security master


class ProspectusQueryEngine:
    """
    RAG engine for querying bond prospectuses.
    Retrieves relevant clauses and generates grounded answers with citations.
    Flags mismatches against security master data automatically.

    # Coupon validation — real-world complexity:
    #
    # Fixed rate bonds:
    #   Security master has a single coupon_rate float (e.g. 3.875)
    #   Prospectus states: "3.875% per annum, semi-annual, 30/360"
    #   Validation: compare rate + frequency + day count convention
    #
    # Floating rate bonds:
    #   Security master has: reference_rate="3M EURIBOR", spread=125,
    #                        day_count="Act/360", reset_freq="quarterly",
    #                        floor=0.0, cap=None
    #   Prospectus states the formula in natural language — RAG must extract
    #   all components and compare each against security master fields
    #   Any single field mismatch → flag the specific field, not just "mismatch"
    #
    # This was a real pain point — quants would manually verify floating rate
    # coupon formulas from prospectuses when Bloomberg feed data showed
    # discrepancies in spread, day count, or reset frequency.

    Usage (planned):
        engine = ProspectusQueryEngine(document_store=store, llm_model="gpt-4")
        result = engine.query(
            isin="XS1234567890",
            question="What is the call schedule for this bond?",
            field="call_schedule"  # optional — specific security master field to compare
        )
        # result = {
        #   "answer": "Per the Offering Circular dated 12 March 2019 (page 147)...",
        #   "sources": [{"page": 147, "document": "OC_2019.pdf", "excerpt": "..."}],
        #   "mismatch_detected": True,
        #   "security_master_value": "par flat",
        #   "prospectus_value": "par + 0.5% call premium"
        # }
    """

    pass  # TODO Day 3
