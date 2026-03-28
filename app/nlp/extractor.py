"""
NLP parameter extractor for Bond Data Intelligence Platform.

Uses OpenAI GPT to extract structured query parameters (ISIN, from_date, to_date)
from natural language input, enabling free-text bond queries.
"""

import json
from datetime import date

from openai import AsyncOpenAI
from pydantic import BaseModel

_SYSTEM_PROMPT = """You are a financial data assistant. Extract bond query parameters from the user's natural language input.

Today's date is 2026-03-28.

Return a JSON object with exactly these keys:
- "isin": the bond ISIN code (12-character alphanumeric, e.g. XS1234567890)
- "from_date": start date in YYYY-MM-DD format
- "to_date": end date in YYYY-MM-DD format

Resolve relative date expressions (e.g. "last quarter", "this year", "last 6 months") using today's date.

If you cannot identify a valid ISIN or a date range, return:
{"error": "reason why extraction failed"}

Do not include any other keys or explanation — return only the JSON object."""


class ExtractedQueryParams(BaseModel):
    """Structured bond query parameters extracted from natural language input."""

    isin: str
    from_date: date
    to_date: date


class NLPExtractor:
    """Extracts structured bond query parameters from free-text using OpenAI GPT."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI()

    async def extract(self, query: str) -> ExtractedQueryParams:
        """Extract ISIN and date range from a natural language query string.

        Args:
            query: Free-text bond query, e.g. "Show me XS1234567890 bonds from Q1 2025"

        Returns:
            ExtractedQueryParams with isin, from_date, to_date.

        Raises:
            ValueError: If the LLM cannot extract a valid ISIN or date range.
        """
        response = await self._client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
        )

        raw = response.choices[0].message.content or ""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned invalid JSON: {raw!r}") from exc

        if "error" in payload:
            raise ValueError(f"LLM could not extract query parameters: {payload['error']}")

        missing = [k for k in ("isin", "from_date", "to_date") if k not in payload]
        if missing:
            raise ValueError(f"LLM response missing required fields: {missing}")

        try:
            return ExtractedQueryParams(
                isin=payload["isin"],
                from_date=payload["from_date"],
                to_date=payload["to_date"],
            )
        except Exception as exc:
            raise ValueError(f"Failed to parse extracted parameters: {exc}") from exc
