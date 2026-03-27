# Day 3 — Document Store
#
# Purpose: Abstraction layer over ChromaDB vector store.
# Provides methods to:
#   - store_document(isin, chunks, embeddings, metadata)
#   - query_document(isin, query_text, top_k=5)
#   - list_documents() — show all ISINs with ingested prospectuses
#   - delete_document(isin) — remove all chunks for an ISIN
#
# ChromaDB chosen for Day 3 because:
#   - Runs locally, no external service needed
#   - Easy to swap for Pinecone/Weaviate in production
#   - Supports metadata filtering (filter by isin, document_type)
#
# TODO Day 3: Implement DocumentStore class


class DocumentStore:
    """
    Abstraction over ChromaDB for bond prospectus storage and retrieval.

    Usage (planned):
        store = DocumentStore(persist_dir="./chroma_db")
        store.store_document(
            isin="XS1234567890",
            chunks=["...text chunk 1...", "...text chunk 2..."],
            embeddings=[[0.1, 0.2, ...], [0.3, 0.4, ...]],
            metadata=[
                {"isin": "XS1234567890", "document_type": "prospectus", "page_number": 147, "source_file": "OC_2019.pdf"},
                {"isin": "XS1234567890", "document_type": "prospectus", "page_number": 148, "source_file": "OC_2019.pdf"},
            ]
        )
        results = store.query_document(isin="XS1234567890", query_text="call schedule", top_k=5)
    """

    pass  # TODO Day 3
