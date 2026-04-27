"""
Day 3 — RAG Query Engine

Given an ISIN and a natural language question, retrieves relevant prospectus
chunks from ChromaDB and generates a grounded answer via GPT-4o-mini.
"""

from openai import AsyncOpenAI
from pydantic import BaseModel

from day3.ingestion.document_store import DocumentStore

_SYSTEM_PROMPT = """You are a financial document analyst. Answer questions based ONLY on the provided prospectus excerpts.

Rules:
1. Use ONLY the information from the context provided below. Never use external knowledge or assumptions.
2. Cite page numbers whenever possible (e.g. "Per page 12 of the prospectus...").
3. If the answer is not present in the context, respond with exactly: "Not found in prospectus"
4. Be precise and concise. Do not speculate."""


class RAGSource(BaseModel):
    """A single source chunk returned by the RAG engine."""

    page: int
    document: str
    excerpt: str


class RAGQueryResult(BaseModel):
    """Full result returned by RAGQueryEngine.query()."""

    answer: str
    sources: list[RAGSource]
    confidence: str  # "high" | "medium" | "low"


class RAGQueryEngine:
    """
    RAG engine for querying bond prospectuses.

    Flow:
      1. Embed the natural language question.
      2. Retrieve top-5 relevant chunks from ChromaDB for the ISIN.
      3. Build a grounded prompt and call GPT-4o-mini.
      4. Return RAGQueryResult with answer, source citations and confidence.
    """

    def __init__(self, document_store: DocumentStore | None = None) -> None:
        self._store = document_store or DocumentStore()
        self._client = AsyncOpenAI()

    async def _embed(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            model="text-embedding-ada-002",
            input=[text],
        )
        return response.data[0].embedding

    def _confidence(self, chunks: list[dict]) -> str:
        """
        Derive a confidence label from the average cosine distance of retrieved chunks.

        With the cosine space used by ChromaDB, 0 = identical and 2 = opposite.
        Typical well-matched results fall in the 0.1 – 0.4 range.
        """
        if not chunks:
            return "low"
        avg_distance = sum(c.get("distance", 1.0) for c in chunks) / len(chunks)
        if avg_distance < 0.3:
            return "high"
        if avg_distance < 0.6:
            return "medium"
        return "low"

    async def query(self, question: str, isin: str) -> RAGQueryResult:
        """
        Answer a natural language question grounded in the prospectus for the given ISIN.

        Raises:
            ValueError: If no documents have been ingested for the ISIN.
        """
        if not self._store.collection_exists(isin):
            raise ValueError(
                f"No documents found for ISIN {isin}. Please ingest prospectus first."
            )

        embedding = await self._embed(question)
        chunks = self._store.query(isin, embedding, n_results=5)

        if not chunks:
            raise ValueError(
                f"No documents found for ISIN {isin}. Please ingest prospectus first."
            )

        context_parts = [
            f"[Page {c['page']} — {c['document']}]\n{c['text']}" for c in chunks
        ]
        context = "\n\n---\n\n".join(context_parts)

        user_prompt = (
            f"Question: {question}\n\n"
            f"Prospectus excerpts for ISIN {isin}:\n\n"
            f"{context}\n\n"
            "Answer the question based solely on the excerpts above. Cite page numbers."
        )

        response = await self._client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        answer = response.choices[0].message.content or "Not found in prospectus"

        sources = [
            RAGSource(
                page=c["page"],
                document=c["document"],
                excerpt=c["text"][:200],
            )
            for c in chunks
        ]

        return RAGQueryResult(
            answer=answer,
            sources=sources,
            confidence=self._confidence(chunks),
        )
