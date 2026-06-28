"""`KPIService` — the FastAPI-facing entry point to the KPI agentic workflow.

Holds the compiled LangGraph and translates HTTP-level calls into graph
invoke/resume operations. Per-email isolation is enforced by deriving the
checkpointer `thread_id` from `email` + `session_id`.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from langgraph.types import Command

logger = logging.getLogger(__name__)

DEFAULT_SESSION = "default"


@dataclass
class KpiResult:
    """Outcome of a chat/resume call, mapped 1:1 onto the API response schema."""

    session_id: str
    status: str  # completed | awaiting_approval | denied | error
    company: dict | None = None
    kpis: str | None = None  # KPI analysis rendered as Markdown
    message: str | None = None
    pending_approval: dict | None = None
    steps: list[dict] = field(default_factory=list)
    took_ms: float = 0.0


class KPIService:
    """Drives the compiled KPI graph for a given user/session thread."""

    def __init__(self, graph) -> None:
        self._graph = graph

    @staticmethod
    def _thread_id(email: str, session_id: str) -> str:
        return f"{email}:{session_id}"

    def chat(
        self,
        email: str,
        symbol: str,
        message: str,
        file_bytes: bytes | None = None,
        file_name: str | None = None,
        session_id: str | None = None,
    ) -> KpiResult:
        session_id = session_id or DEFAULT_SESSION
        config = {"configurable": {"thread_id": self._thread_id(email, session_id)}}
        # Provide only the new turn's inputs; prior company/document context is
        # restored from the checkpoint, giving per-email chat memory.
        inputs: dict[str, Any] = {
            "email": email,
            "session_id": session_id,
            "symbol": symbol,
            "message": message,
            "user_file_bytes": file_bytes,
            "user_file_name": file_name,
            # Reset per-turn outcome channels so a prior turn doesn't leak through.
            "status": "",
            "denial_reason": None,
            "message_out": None,
            "kpis": None,
        }
        logger.info("KPI chat — email=%s symbol=%s session=%s", email, symbol, session_id)
        start = time.perf_counter()
        result = self._graph.invoke(inputs, config=config)
        return self._to_result(session_id, result, start)

    def resume(
        self,
        email: str,
        session_id: str,
        interrupt_id: str,
        decision: str,
        feedback: str | None = None,
    ) -> KpiResult:
        config = {"configurable": {"thread_id": self._thread_id(email, session_id)}}
        logger.info(
            "KPI resume — email=%s session=%s decision=%s", email, session_id, decision
        )
        start = time.perf_counter()
        result = self._graph.invoke(
            Command(resume={"decision": decision, "feedback": feedback}),
            config=config,
        )
        return self._to_result(session_id, result, start)

    def _to_result(self, session_id: str, result: dict, start: float) -> KpiResult:
        took_ms = (time.perf_counter() - start) * 1000.0
        steps = result.get("steps", [])
        logger.info(
            "[kpi:service] graph returned status=%s through %d step(s) in %.1fms",
            result.get("status") or ("awaiting_approval" if result.get("__interrupt__") else "completed"),
            len(steps),
            took_ms,
        )

        interrupts = result.get("__interrupt__")
        if interrupts:
            intr = interrupts[0]
            payload = getattr(intr, "value", {}) or {}
            interrupt_id = getattr(intr, "id", None) or getattr(intr, "interrupt_id", None)
            logger.info("[kpi:service] AWAITING_APPROVAL interrupt_id=%s", interrupt_id)
            return KpiResult(
                session_id=session_id,
                status="awaiting_approval",
                company=payload.get("company"),
                message=payload.get("summary"),
                pending_approval={
                    "interrupt_id": interrupt_id,
                    "summary": payload.get("summary"),
                },
                steps=steps,
                took_ms=took_ms,
            )

        return KpiResult(
            session_id=session_id,
            status=result.get("status") or "completed",
            company=result.get("company"),
            kpis=result.get("kpis"),
            message=result.get("message_out"),
            steps=steps,
            took_ms=took_ms,
        )