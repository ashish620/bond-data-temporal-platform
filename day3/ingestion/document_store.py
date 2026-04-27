"""
Day 3 — Document Store

Abstraction layer over ChromaDB for bond prospectus storage and retrieval.
Collections are named bonds_{isin}, e.g. bonds_XS1234567890.
"""

import os

import chromadb


class DocumentStore:
    """
    Abstraction over ChromaDB for bond prospectus storage and retrieval.

    Each ISIN gets its own ChromaDB collection named bonds_{isin}.
    Chunks are stored with their pre-computed embeddings and metadata.
    """

    def __init__(self, persist_dir: str | None = None) -> None:
        self._persist_dir = persist_dir or os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        self._client = chromadb.PersistentClient(path=self._persist_dir)

    def _collection_name(self, isin: str) -> str:
        return f"bonds_{isin}"

    def get_or_create_collection(self, isin: str) -> chromadb.Collection:
        """Return (or create) the ChromaDB collection for the given ISIN."""
        return self._client.get_or_create_collection(
            name=self._collection_name(isin),
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, isin: str, chunks: list[dict]) -> None:
        """
        Store pre-embedded chunks in the collection for the given ISIN.

        Each chunk dict must contain: text, page, document, chunk_id, embedding.
        """
        collection = self.get_or_create_collection(isin)
        collection.add(
            ids=[chunk["chunk_id"] for chunk in chunks],
            embeddings=[chunk["embedding"] for chunk in chunks],
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[
            {
                "page": chunk["page"],
                "document": chunk["document"],
                **( {"document_type": chunk["document_type"]} if chunk.get("document_type") else {} ),
            }
            for chunk in chunks
        ],
        )

    def query(self, isin: str, query_embedding: list[float], n_results: int = 5) -> list[dict]:
        """
        Retrieve the top-n most relevant chunks for the given ISIN.

        Returns a list of dicts with keys: text, page, document, distance.
        """
        collection = self.get_or_create_collection(isin)
        count = collection.count()
        if count == 0:
            return []
        effective_n = min(n_results, count)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=effective_n,
        )
        chunks: list[dict] = []
        for i, doc in enumerate(results["documents"][0]):  # type: ignore[index]
            meta = results["metadatas"][0][i]  # type: ignore[index]
            distance = (
                results["distances"][0][i]  # type: ignore[index]
                if results.get("distances")
                else 1.0
            )
            chunks.append(
                {
                    "text": doc,
                    "page": meta.get("page", 0),
                    "document": meta.get("document", ""),
                    "distance": distance,
                }
            )
        return chunks

    def collection_exists(self, isin: str) -> bool:
        """Return True if the collection for the given ISIN has at least one document."""
        try:
            collection = self._client.get_collection(self._collection_name(isin))
            return collection.count() > 0
        except Exception:
            return False

    def delete_collection(self, isin: str) -> None:
        """Delete the collection for the given ISIN (used for re-ingestion)."""
        try:
            self._client.delete_collection(self._collection_name(isin))
        except Exception:
            pass
