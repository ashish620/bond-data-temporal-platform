"""
Day 4 — Reconciliation Agent.

One instance per mismatched record.  Multiple instances run concurrently
(via asyncio.gather in the ingestor/event-bus handler) — one per event.

Phases
------
1. PLAN     — LLM decides which sources are worth querying for each mismatched field.
2. EXECUTE  — Fetch data from decided sources concurrently.
3. VALIDATE — LLM assesses consistency for each mismatched field concurrently.
4. RESOLVE  — Convert assessments to AgentRecommendation objects; LLM writes summary.
"""

import asyncio
import json
import logging
from datetime import datetime
from uuid import uuid4

from openai import AsyncOpenAI

from app.router import TemporalRouter
from day3.rag.query_engine import RAGQueryEngine
from day4.agent.tools import (
    assess_field_consistency,
    fetch_from_current_db,
    fetch_from_legacy_db,
    query_prospectus,
)
from day4.models import (
    AgentRecommendation,
    ReconciliationEvent,
    ReconciliationFinding,
)

logger = logging.getLogger(__name__)

_CONFIDENCE_MAP = {"high": "high", "medium": "medium", "low": "low"}


class ReconciliationAgent:
    """
    Single agent instance handling one ReconciliationEvent.

    Runs 4 phases sequentially (each phase depends on the previous):
      Phase 1 — PLAN:     Decide which sources to query per mismatch.
      Phase 2 — EXECUTE:  Fetch data from decided sources concurrently.
      Phase 3 — VALIDATE: Assess consistency for each field concurrently.
      Phase 4 — RESOLVE:  Build final recommendations and summary.

    Many instances run concurrently — one per mismatched record.
    """

    def __init__(
        self,
        event: ReconciliationEvent,
        router: TemporalRouter,
        rag_engine: RAGQueryEngine,
    ) -> None:
        self.event = event
        self._router = router
        self._rag_engine = rag_engine
        self._client = AsyncOpenAI()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self) -> ReconciliationFinding:
        """Execute all 4 phases and return a ReconciliationFinding."""
        phase_trace: dict = {}

        # Phase 1: PLAN
        plan = await self._plan()
        phase_trace["plan"] = plan

        # Phase 2: EXECUTE (concurrent fetches)
        execution_data = await self._execute(plan)
        phase_trace["execute"] = {"sources_queried": list(execution_data.keys())}

        # Phase 3: VALIDATE (concurrent assessments)
        validations = await self._validate(execution_data)
        phase_trace["validate"] = {"fields_assessed": len(validations)}

        # Phase 4: RESOLVE
        recommendations, summary = await self._resolve(validations)
        phase_trace["resolve"] = {"recommendation_count": len(recommendations)}

        return ReconciliationFinding(
            finding_id=str(uuid4()),
            event_id=self.event.event_id,
            isin=self.event.isin,
            snapshot_date=self.event.snapshot_date,
            recommendations=recommendations,
            overall_summary=summary,
            agent_phases=phase_trace,
            created_at=datetime.utcnow(),
            status="PENDING",
        )

    # ------------------------------------------------------------------
    # Phase 1 — PLAN
    # ------------------------------------------------------------------

    async def _plan(self) -> dict:
        """
        Use the LLM to decide which sources to query for the detected mismatches.

        Returns a dict such as::

            {
                "check_legacy": true,
                "check_current": true,
                "check_prospectus": true,
                "fields_to_prospect": ["coupon_rate", "maturity_date"]
            }
        """
        mismatched_fields = [m.field for m in self.event.mismatches]

        system_prompt = (
            "You are a bond data reconciliation planner. "
            "Given a list of mismatched fields for a bond ISIN, decide which data sources "
            "should be queried to resolve the discrepancies. Return ONLY a JSON object with "
            "four keys: check_legacy (bool), check_current (bool), check_prospectus (bool), "
            "fields_to_prospect (array of field names to look up in the prospectus). "
            "Return only the fields that have mismatches in fields_to_prospect."
        )

        user_prompt = (
            f"ISIN: {self.event.isin}\n"
            f"Mismatched fields: {mismatched_fields}\n\n"
            "Which sources should the agent query to resolve these mismatches? Return JSON only."
        )

        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            raw = response.choices[0].message.content or "{}"
            plan = json.loads(raw)
            # Ensure required keys with safe defaults
            plan.setdefault("check_legacy", True)
            plan.setdefault("check_current", True)
            plan.setdefault("check_prospectus", True)
            plan.setdefault("fields_to_prospect", mismatched_fields)
            logger.debug("Agent %s — plan: %s", self.event.event_id, plan)
            return plan
        except Exception:  # noqa: BLE001
            logger.exception("Agent %s — _plan failed; using defaults", self.event.event_id)
            return {
                "check_legacy": True,
                "check_current": True,
                "check_prospectus": True,
                "fields_to_prospect": mismatched_fields,
            }

    # ------------------------------------------------------------------
    # Phase 2 — EXECUTE
    # ------------------------------------------------------------------

    async def _execute(self, plan: dict) -> dict:
        """
        Concurrently fetch data from all sources decided in the plan.

        Returns a dict keyed by source name, e.g.::

            {
                "legacy":     [snapshot dicts …],
                "current":    [snapshot dicts …],
                "prospectus": {"coupon_rate": {answer, confidence, sources}, …},
            }
        """
        tasks: dict[str, asyncio.Task] = {}

        if plan.get("check_legacy"):
            tasks["legacy"] = asyncio.ensure_future(
                fetch_from_legacy_db(self.event.isin, self._router)
            )

        if plan.get("check_current"):
            tasks["current"] = asyncio.ensure_future(
                fetch_from_current_db(self.event.isin, self._router)
            )

        prospectus_fields = plan.get("fields_to_prospect", [])
        if plan.get("check_prospectus") and prospectus_fields:
            async def _fetch_all_prospectus_fields() -> dict:
                results = await asyncio.gather(
                    *(
                        query_prospectus(self.event.isin, field, self._rag_engine)
                        for field in prospectus_fields
                    ),
                    return_exceptions=True,
                )
                return {
                    field: (r if not isinstance(r, Exception) else {"answer": "Not found in prospectus", "confidence": "low", "sources": []})
                    for field, r in zip(prospectus_fields, results)
                }

            tasks["prospectus"] = asyncio.ensure_future(_fetch_all_prospectus_fields())

        if not tasks:
            return {}

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        execution_data = {}
        for key, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.warning("Agent %s — execute task '%s' raised: %s", self.event.event_id, key, result)
                execution_data[key] = [] if key != "prospectus" else {}
            else:
                execution_data[key] = result

        return execution_data

    # ------------------------------------------------------------------
    # Phase 3 — VALIDATE
    # ------------------------------------------------------------------

    async def _validate(self, execution_data: dict) -> list[dict]:
        """
        Concurrently assess each mismatched field using all available data.

        Returns a list of raw assessment dicts, one per mismatched field.
        """
        legacy_snapshots: list[dict] = execution_data.get("legacy", [])
        current_snapshots: list[dict] = execution_data.get("current", [])
        prospectus_data: dict = execution_data.get("prospectus", {})

        async def _assess_one(mismatch) -> dict:
            # Collect historical values for this field from legacy + current
            all_snapshots = legacy_snapshots + current_snapshots
            historical_values = [
                snap.get(mismatch.field) for snap in all_snapshots if mismatch.field in snap
            ]

            prospectus_result = prospectus_data.get(mismatch.field, {})
            prospectus_answer = prospectus_result.get("answer", "Not found in prospectus")

            assessment = await assess_field_consistency(
                field=mismatch.field,
                incoming_value=mismatch.incoming_value,
                master_value=mismatch.master_value,
                legacy_values=historical_values,
                prospectus_answer=prospectus_answer,
                client=self._client,
            )
            assessment["field"] = mismatch.field
            assessment["incoming_value"] = mismatch.incoming_value
            assessment["master_value"] = mismatch.master_value
            assessment["prospectus_confidence"] = prospectus_result.get("confidence", "low")
            return assessment

        validations = await asyncio.gather(
            *(_assess_one(m) for m in self.event.mismatches),
            return_exceptions=True,
        )

        cleaned = []
        for v, mismatch in zip(validations, self.event.mismatches):
            if isinstance(v, Exception):
                logger.warning(
                    "Agent %s — validate for field '%s' raised: %s",
                    self.event.event_id,
                    mismatch.field,
                    v,
                )
                cleaned.append({
                    "field": mismatch.field,
                    "incoming_value": mismatch.incoming_value,
                    "master_value": mismatch.master_value,
                    "recommended_action": "MANUAL_REVIEW",
                    "reasoning": "Validation failed — manual review required.",
                    "prospectus_value": None,
                    "prospectus_confidence": "low",
                })
            else:
                cleaned.append(v)

        return cleaned

    # ------------------------------------------------------------------
    # Phase 4 — RESOLVE
    # ------------------------------------------------------------------

    async def _resolve(self, validations: list[dict]) -> tuple[list[AgentRecommendation], str]:
        """
        Build AgentRecommendation objects and generate an overall LLM summary.

        Returns:
            (recommendations, overall_summary)
        """
        recommendations: list[AgentRecommendation] = []

        for v in validations:
            # Map raw assessment to recommendation model
            action = v.get("recommended_action", "MANUAL_REVIEW")
            if action not in ("ACCEPT_INCOMING", "KEEP_MASTER", "MANUAL_REVIEW"):
                action = "MANUAL_REVIEW"

            # Derive confidence from prospectus confidence + action certainty
            p_conf = v.get("prospectus_confidence", "low")
            if action == "MANUAL_REVIEW":
                confidence = "low"
            elif p_conf == "high":
                confidence = "high"
            elif p_conf == "medium":
                confidence = "medium"
            else:
                confidence = "low"

            recommendations.append(
                AgentRecommendation(
                    field=v["field"],
                    incoming_value=v["incoming_value"],
                    master_value=v["master_value"],
                    prospectus_value=v.get("prospectus_value"),
                    recommended_action=action,
                    reasoning=v.get("reasoning", ""),
                    confidence=confidence,
                )
            )

        summary = await self._generate_summary(recommendations)
        return recommendations, summary

    async def _generate_summary(self, recommendations: list[AgentRecommendation]) -> str:
        """Ask the LLM to write a plain-English summary of all findings."""
        if not recommendations:
            return "No mismatches detected."

        rec_lines = "\n".join(
            f"- {r.field}: {r.recommended_action} (confidence: {r.confidence}) — {r.reasoning}"
            for r in recommendations
        )

        user_prompt = (
            f"ISIN: {self.event.isin}\n"
            f"Snapshot date: {self.event.snapshot_date}\n\n"
            f"Field-level recommendations:\n{rec_lines}\n\n"
            "Write a concise 2–3 sentence summary of the reconciliation findings for a data "
            "operations analyst. Highlight the most important action required."
        )

        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a bond data operations analyst."},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content or "Summary unavailable."
        except Exception:  # noqa: BLE001
            logger.exception("Agent %s — _generate_summary failed", self.event.event_id)
            return (
                f"Reconciliation found {len(recommendations)} field mismatch(es) for "
                f"{self.event.isin} on {self.event.snapshot_date}. Manual review recommended."
            )
