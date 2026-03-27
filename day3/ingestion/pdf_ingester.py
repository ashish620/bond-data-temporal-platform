# Day 3 — PDF Ingestion Pipeline
#
# Purpose: Ingest bond prospectuses and certificates as PDFs, chunk them,
# embed them, and store in a vector database (ChromaDB) keyed by ISIN.
#
# Flow:
#   1. Accept PDF file + ISIN identifier
#   2. Extract text using pypdf
#   3. Chunk text into overlapping windows (chunk_size=1000, overlap=200)
#      — overlap ensures call/put schedules spanning page breaks are captured
#   4. Embed each chunk using OpenAI text-embedding-ada-002
#      or sentence-transformers/all-MiniLM-L6-v2 (open source alternative)
#   5. Store in ChromaDB with metadata: {isin, document_type, page_number, source_file}
#
# TODO Day 3: Implement PDFIngester class
# TODO Day 3: Add support for batch ingestion of multiple ISINs
# TODO Day 3: Add document_type classification
#             (prospectus / final_terms / pricing_supplement / corporate_action)


class PDFIngester:
    """
    Ingests bond prospectus PDFs into ChromaDB vector store.
    Keyed by ISIN so queries can be scoped to a specific bond.

    Usage (planned):
        ingester = PDFIngester(document_store=store, embedding_model="openai")
        ingester.ingest(
            pdf_path="prospectuses/XS1234567890_offering_circular.pdf",
            isin="XS1234567890",
            document_type="prospectus"
        )
    """

    pass  # TODO Day 3
