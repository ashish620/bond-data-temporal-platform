"""
Day 3 — PDF Ingestion Pipeline

Loads bond prospectus PDFs, chunks them with a sliding window, embeds each
chunk using OpenAI text-embedding-ada-002, and stores them in ChromaDB via
DocumentStore keyed by ISIN.
"""

import os
import uuid

from openai import AsyncOpenAI, OpenAI
from pypdf import PdfReader

from day3.ingestion.document_store import DocumentStore


class PDFIngester:
    """
    Ingests bond prospectus PDFs into ChromaDB vector store.

    Text is extracted page-by-page via pypdf, split into overlapping windows
    (chunk_size=1000 chars, overlap=200 chars), embedded with OpenAI
    text-embedding-ada-002, and stored in DocumentStore.
    """

    CHUNK_SIZE = 1000
    OVERLAP = 200

    def __init__(self, document_store: DocumentStore | None = None) -> None:
        self._store = document_store or DocumentStore()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_pages(self, pdf_path: str) -> list[tuple[int, str]]:
        """Return a list of (page_number, text) tuples (1-indexed pages)."""
        reader = PdfReader(pdf_path)
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]

    def _chunk_pages(self, pages: list[tuple[int, str]], document: str, document_type: str = "prospectus") -> list[dict]:
        """Split page text into overlapping chunks and attach metadata."""
        chunks: list[dict] = []
        for page_num, text in pages:
            start = 0
            while start < len(text):
                end = start + self.CHUNK_SIZE
                chunk_text = text[start:end].strip()
                if chunk_text:
                    chunks.append(
                        {
                            "text": chunk_text,
                            "page": page_num,
                            "document": document,
                            "document_type": document_type,
                            "chunk_id": str(uuid.uuid4()),
                        }
                    )
                start += self.CHUNK_SIZE - self.OVERLAP
        return chunks

    def _embed_chunks_sync(self, chunks: list[dict]) -> list[dict]:
        """Embed all chunks in a single batched OpenAI call (sync)."""
        client = OpenAI()
        texts = [chunk["text"] for chunk in chunks]
        response = client.embeddings.create(model="text-embedding-ada-002", input=texts)
        for i, chunk in enumerate(chunks):
            chunk["embedding"] = response.data[i].embedding
        return chunks

    async def _embed_chunks_async(self, chunks: list[dict]) -> list[dict]:
        """Embed all chunks in a single batched OpenAI call (async)."""
        client = AsyncOpenAI()
        texts = [chunk["text"] for chunk in chunks]
        response = await client.embeddings.create(model="text-embedding-ada-002", input=texts)
        for i, chunk in enumerate(chunks):
            chunk["embedding"] = response.data[i].embedding
        return chunks

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ingest(
        self,
        pdf_path: str,
        isin: str,
        document_type: str = "prospectus",
        force: bool = False,
    ) -> int:
        """
        Ingest a PDF prospectus for the given ISIN.

        Skips ingestion if the ISIN already has documents in the store unless
        force=True.  Returns the number of chunks stored.
        """
        if not force and self._store.collection_exists(isin):
            return 0

        document = os.path.basename(pdf_path)
        pages = self._extract_pages(pdf_path)
        chunks = self._chunk_pages(pages, document, document_type)

        if not chunks:
            return 0

        chunks = await self._embed_chunks_async(chunks)
        self._store.add_chunks(isin, chunks)
        return len(chunks)

    def ingest_sync(
        self,
        pdf_path: str,
        isin: str,
        document_type: str = "prospectus",
        force: bool = False,
    ) -> int:
        """Synchronous variant of ingest — suitable for CLI / seed scripts."""
        if not force and self._store.collection_exists(isin):
            return 0

        document = os.path.basename(pdf_path)
        pages = self._extract_pages(pdf_path)
        chunks = self._chunk_pages(pages, document, document_type)

        if not chunks:
            return 0

        chunks = self._embed_chunks_sync(chunks)
        self._store.add_chunks(isin, chunks)
        return len(chunks)
