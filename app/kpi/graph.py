"""The KPI agentic workflow as a LangGraph `StateGraph`.

Decoupled from FastAPI: nodes operate on `KpiState` and reach the outside world
only through injected seams (`KpiRepository`, `BaseLLM`, `DataStorage`,
`KpiRegistry`). The compiled graph gets first-class per-email persistence (via the
checkpointer keyed by `thread_id`) and human-in-the-loop pauses (via `interrupt`).

Pipeline: finance_guardrail -> resolve_company -> authorize -> fetch_documents ->
retrieve_document -> parse_document -> map_kpis -> build_prompt -> human_approval
-> generate_kpis -> persist.
"""
import json
import logging
import operator
import re
from dataclasses import asdict, dataclass
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.core.interfaces import BaseLLM
from app.core.kpi_repository import DocumentRef, KpiRepository
from app.core.parsers import get_parser
from app.exceptions import RAGException
from app.kpi.registry import KpiRegistry
from nse_data_storage import DataStorage

logger = logging.getLogger(__name__)

# The exact guardrail message mandated by the spec — returned verbatim on denial.
DENIAL_MESSAGE = "The Analysis of this company is not in your scope"

# Returned when the request is not about finance / financial analysis (workflow step 1).
NON_FINANCE_MESSAGE = (
    "I can only help with financial analysis and KPIs for companies in your scope. "
    "Please ask a finance-related question."
)

_FINANCE_GUARDRAIL_SYSTEM = (
    "You are a strict domain classifier for a financial-analysis assistant. "
    "Decide whether the user's message is about finance: company financial "
    "performance, financial statements, KPIs, ratios, earnings, valuation, or "
    "investing. Reply with ONLY one word: YES if it is finance-related, or NO if "
    "it is not."
)

# Document-type preference when ranking candidate filings.
_TYPE_PRIORITY = {"annual_report": 3, "financial_result": 2, "announcement": 1}


class KpiState(TypedDict, total=False):
    """Channels threaded through the graph; persisted per `thread_id`."""

    email: str
    session_id: str
    symbol: str | None
    message: str

    company: dict | None
    authorized: bool

    candidate_documents: list[dict]
    selected_document: dict | None
    bucket: str | None
    # Retrieved file blobs (all forwarded documents): [{"filename", "bytes"}].
    document_blobs: list[dict] | None
    document_text: str | None

    user_file_bytes: bytes | None
    user_file_name: str | None
    user_file_text: str | None

    requested_categories: dict
    requested_kpis: list[str]
    kpi_prompt: str | None
    # Final KPI report rendered as Markdown (the model emits Markdown, not JSON).
    kpis: str | None

    status: str
    denial_reason: str | None
    message_out: str | None

    # Reducer channels: appended to across nodes / turns.
    steps: Annotated[list[dict], operator.add]
    messages: Annotated[list[dict], operator.add]


def _step(node: str, summary: str) -> dict:
    return {"node": node, "summary": summary}


@dataclass
class KpiNodes:
    """Holds the injected seams and implements each graph node."""

    repository: KpiRepository
    llm: BaseLLM
    storage: DataStorage
    registry: KpiRegistry
    prompt_template: str
    require_approval: bool = True
    admin_bypass: bool = False
    # Cap the parsed document text injected into the LLM prompt. Annual reports
    # are huge; without a budget the request can exceed the model/provider token
    # limit and the LLM API rejects it (e.g. HF 400 Bad Request). 0 = unbounded.
    max_document_chars: int = 24000

    # --- 1. finance_guardrail (DOMAIN GUARDRAIL) ----------------------------

    def finance_guardrail(self, state: KpiState) -> dict:
        message = state["message"]
        logger.info("[kpi:finance_guardrail] START message=%r", message)
        if self._is_finance_related(message):
            logger.info("[kpi:finance_guardrail] DONE finance-related; proceeding")
            return {"steps": [_step("finance_guardrail", "Request is finance-related; proceeding")]}
        logger.warning("[kpi:finance_guardrail] DENIED non-finance message — halting before resolve")
        return {
            "status": "denied",
            "denial_reason": NON_FINANCE_MESSAGE,
            "message_out": NON_FINANCE_MESSAGE,
            "steps": [_step("finance_guardrail", "Denied — message is not finance-related")],
        }

    def _is_finance_related(self, message: str) -> bool:
        try:
            raw = self.llm.complete(_FINANCE_GUARDRAIL_SYSTEM, message).strip()
        except Exception as exc:  # noqa: BLE001 — fail open so the classifier never blocks legit use
            logger.warning("[kpi:finance_guardrail] classifier failed (%s); failing open", exc)
            return True
        verdict = raw.strip().strip('"').strip().upper()
        logger.debug("[kpi:finance_guardrail] classifier verdict=%r", verdict)
        if verdict.startswith("NO") or "NOT_FINANCE" in verdict or "UNRELATED" in verdict:
            return False
        return True

    # --- 2. resolve_company -------------------------------------------------

    def resolve_company(self, state: KpiState) -> dict:
        symbol = (state.get("symbol") or "").strip()
        logger.info(
            "[kpi:resolve_company] START email=%s symbol=%r",
            state.get("email"),
            symbol,
        )
        # The request carries the company symbol; resolve the full company
        # (id + name + canonical symbol) directly from the DB — no LLM call.
        company: dict | None = None
        if symbol:
            matches = self.repository.find_company(symbol)
            logger.info(
                "[kpi:resolve_company] DB lookup for %r returned %d match(es)",
                symbol,
                len(matches),
            )
            if matches:
                m = matches[0]
                company = {
                    "id": m["id"],
                    "symbol": m["symbol"],
                    "company_name": m["company_name"],
                }
        # On a follow-up turn the request may omit the symbol — reuse prior context.
        if company is None and state.get("company"):
            company = state.get("company")
            logger.info("[kpi:resolve_company] Reusing prior company from memory: %s", company)
        if company is None:
            logger.warning("[kpi:resolve_company] DENIED-PATH no company resolved (symbol=%r)", symbol)
            return {
                "status": "error",
                "message_out": (
                    "I couldn't identify which company you're asking about. "
                    "Please provide a valid company stock symbol."
                ),
                "steps": [_step("resolve_company", f"No company resolved from symbol {symbol!r}")],
            }
        logger.info(
            "[kpi:resolve_company] DONE resolved company_id=%s symbol=%s",
            company["id"],
            company["symbol"],
        )
        return {
            "company": company,
            "steps": [_step("resolve_company", f"Resolved {company['symbol']} ({company['company_name']})")],
        }

    # --- 3. authorize (GUARDRAIL) ------------------------------------------

    def authorize(self, state: KpiState) -> dict:
        email = state["email"]
        company = state["company"]
        logger.info(
            "[kpi:authorize] START email=%s company_id=%s symbol=%s",
            email,
            company["id"],
            company.get("symbol"),
        )
        user = self.repository.get_user_by_email(email)
        if user is None:
            logger.warning("[kpi:authorize] No user row for email=%s", email)
        authorized = False
        if user:
            if self.admin_bypass and (user.get("role") == "admin"):
                authorized = True
                logger.info("[kpi:authorize] Admin bypass granted for user_id=%s", user["id"])
            else:
                authorized = self.repository.is_user_authorized(user["id"], company["id"])
                logger.info(
                    "[kpi:authorize] Watchlist check user_id=%s company_id=%s -> %s",
                    user["id"],
                    company["id"],
                    authorized,
                )
        if not authorized:
            logger.warning(
                "[kpi:authorize] DENIED (fail-closed) email=%s company_id=%s — halting before fetch/LLM",
                email,
                company["id"],
            )
            return {
                "authorized": False,
                "status": "denied",
                "denial_reason": DENIAL_MESSAGE,
                "message_out": DENIAL_MESSAGE,
                "steps": [_step("authorize", "Denied — no active watchlist mapping (fail-closed)")],
            }
        logger.info("[kpi:authorize] DONE authorized email=%s for %s", email, company["symbol"])
        return {
            "authorized": True,
            "steps": [_step("authorize", f"Authorized {email} for {company['symbol']}")],
        }

    # --- 4. fetch_documents -------------------------------------------------

    def fetch_documents(self, state: KpiState) -> dict:
        company = state["company"]
        logger.info(
            "[kpi:fetch_documents] START company_id=%s symbol=%s",
            company["id"],
            company.get("symbol"),
        )
        refs = self.repository.find_company_documents(company["id"], company.get("symbol"))
        # Ranking disabled — forward ALL documents to the next state as-is.
        # ranked = self._rank_documents(refs, state["message"])
        candidates = [asdict(r) for r in refs]
        out: dict[str, Any] = {
            "candidate_documents": candidates,
            "bucket": company.get("symbol"),
        }
        if candidates:
            # selected_document is just the representative shown in the HITL summary;
            # retrieval/parsing below consume every candidate.
            out["selected_document"] = candidates[0]
            logger.info(
                "[kpi:fetch_documents] DONE forwarding all %d document(s) (ranking disabled)",
                len(candidates),
            )
            out["steps"] = [
                _step("fetch_documents", f"Forwarding {len(candidates)} document(s) (ranking disabled)")
            ]
        else:
            out["selected_document"] = None
            logger.warning("[kpi:fetch_documents] DONE no candidate documents for company_id=%s", company["id"])
            out["steps"] = [_step("fetch_documents", "No candidate documents found for company")]
        return out

    # Document ranking is disabled: fetch_documents now forwards all candidate
    # documents to the next state unranked. Kept here (commented) for easy re-enable.
    # def _rank_documents(self, refs: list[DocumentRef], message: str) -> list[DocumentRef]:
    #     msg = (message or "").lower()
    #     years = re.findall(r"(?:19|20)\d{2}", message or "")
    #     wants_consolidated = "consolidated" in msg
    #     wants_audited = "audited" in msg
    #
    #     def score(ref: DocumentRef) -> tuple:
    #         s = 0
    #         if ref.storage_id:  # only pointers we can actually retrieve are useful
    #             s += 5
    #         s += _TYPE_PRIORITY.get(ref.document_type or "", 0)
    #         if ref.year and any(y in str(ref.year) for y in years):
    #             s += 4
    #         extra = ref.extra or {}
    #         if wants_consolidated and str(extra.get("consolidated", "")).lower() in {"true", "yes", "1", "consolidated"}:
    #             s += 2
    #         if wants_audited and str(extra.get("audited", "")).lower() in {"true", "yes", "1", "audited"}:
    #             s += 2
    #         # Tie-break: most recent year first.
    #         year_key = ref.year or ""
    #         return (s, year_key)
    #
    #     return sorted(refs, key=score, reverse=True)

    # --- 5. retrieve_document ----------------------------------------------

    def retrieve_document(self, state: KpiState) -> dict:
        candidates = state.get("candidate_documents") or []
        bucket = state.get("bucket")
        logger.info("[kpi:retrieve_document] START %d candidate(s) bucket=%r", len(candidates), bucket)
        blobs: list[dict] = []
        for doc in candidates:
            storage_id = doc.get("storage_id")
            if not storage_id:
                logger.info("[kpi:retrieve_document] skip doc #%s — no storage pointer", doc.get("document_id"))
                continue
            data = self._retrieve(storage_id, bucket)
            if data is None:
                logger.warning("[kpi:retrieve_document] pointer %r not retrievable; skipping", storage_id)
                continue
            blobs.append({"filename": doc.get("filename"), "bytes": data})
            logger.info("[kpi:retrieve_document] retrieved %d bytes for %r filename %s ", len(data), storage_id, doc.get("filename") )
        logger.info(
            "[kpi:retrieve_document] DONE retrieved %d of %d document(s)", len(blobs), len(candidates)
        )
        return {
            "document_blobs": blobs,
            "steps": [_step("retrieve_document", f"Retrieved {len(blobs)} of {len(candidates)} document(s)")],
        }

    def _retrieve(self, storage_id: str, bucket: str | None) -> bytes | None:
        # Try the company bucket first, then fall back to the default location.
        for b in (bucket, None) if bucket else (None,):
            try:
                logger.debug("[kpi:retrieve_document] storage.retrieve(%r, bucket=%r)", storage_id, b)
                return self.storage.retrieve(storage_id, b)
            except FileNotFoundError:
                logger.debug("[kpi:retrieve_document] not found in bucket=%r", b)
                continue
            except Exception as exc:  # noqa: BLE001 — storage failures are non-fatal here
                logger.warning("[kpi:retrieve_document] storage retrieve failed for %s: %s", storage_id, exc)
                return None
        return None

    # --- 6. parse_document --------------------------------------------------

    def parse_document(self, state: KpiState) -> dict:
        blobs = state.get("document_blobs") or []
        logger.info(
            "[kpi:parse_document] START %d filing(s)",
            len(blobs)
        )
        # Parse every forwarded document and concatenate, headed by its filename.
        sections: list[str] = []
        for blob in blobs:
            text = self._parse(blob.get("bytes"), blob.get("filename"))
            if text:
                sections.append(f"### {blob.get('filename') or 'document'}\n{text}")
        document_text = "\n\n".join(sections) if sections else None
        summary_bits = []
        if document_text:
            summary_bits.append(f"{len(sections)} filing(s)={len(document_text)} chars")
        summary = "Parsed " + (", ".join(summary_bits) if summary_bits else "no document text")
        logger.info("[kpi:parse_document] DONE %s", summary)
        return {
            "document_text": document_text,
            "document_blobs": None,  # drop bytes from persisted state
            "steps": [_step("parse_document", summary)],
        }

    def _parse(self, data: bytes | None, filename: str | None) -> str | None:
        if not data:
            return None
        name = filename or "document"
        try:
            text = get_parser(name).parse(data, name)
        except RAGException as exc:
            logger.warning("[kpi:parse_document] could not parse %s: %s", name, exc.message)
            return None
        cleaned = self._preprocess(text)
        logger.debug("[kpi:parse_document] parsed %s -> %d chars", name, len(cleaned))
        return cleaned

    @staticmethod
    def _preprocess(text: str) -> str:
        # Collapse runs of blank lines / whitespace introduced by extraction.
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    # --- 7. map_kpis --------------------------------------------------------

    def map_kpis(self, state: KpiState) -> dict:
        logger.info("[kpi:map_kpis] START message=%r", state.get("message"))
        categories = self.registry.match_categories(state["message"])
        kpis = [k for kpis in categories.values() for k in kpis]
        logger.info(
            "[kpi:map_kpis] DONE matched %d categor(ies) %s, %d KPI(s)",
            len(categories),
            list(categories.keys()),
            len(kpis),
        )
        return {
            "requested_categories": categories,
            "requested_kpis": kpis,
            "steps": [
                _step(
                    "map_kpis",
                    f"Mapped to {len(categories)} categor(ies), {len(kpis)} KPI(s)",
                )
            ],
        }

    # --- 8. build_prompt ----------------------------------------------------

    def build_prompt(self, state: KpiState) -> dict:
        categories = state.get("requested_categories") or self.registry.categories
        registry_block = self.registry.as_prompt_block(categories)
        parts = [
            "## KPI Registry (allow-list — compute ONLY these KPIs with respective KPI Unit of measurements)",
            registry_block,
        ]
        document_text = self._cap(state.get("document_text"))
        if document_text:
            parts += ["## Company Filing (source of truth for values)", document_text]

        parts += ["## User Request", state["message"]]
        kpi_prompt = "\n\n".join(parts)
        logger.info(
            "[kpi:build_prompt] DONE prompt=%d chars (filing=%s, %d categor(ies))",
            len(kpi_prompt),
            bool(document_text),
            len(categories),
        )
        return {
            "kpi_prompt": kpi_prompt,
            "steps": [_step("build_prompt", f"Built prompt ({len(kpi_prompt)} chars)")],
        }

    def _cap(self, text: str | None) -> str | None:
        """Truncate document text to the configured budget to keep the prompt
        within the LLM/provider token limit."""
        if not text or self.max_document_chars <= 0 or len(text) <= self.max_document_chars:
            return text
        logger.warning(
            "[kpi:build_prompt] document text %d chars exceeds budget %d — truncating",
            len(text),
            self.max_document_chars,
        )
        return text[: self.max_document_chars] + "\n\n[...truncated...]"

    # --- 9. human_approval (HITL) ------------------------------------------

    def human_approval(self, state: KpiState) -> dict:
        if not self.require_approval:
            logger.info("[kpi:human_approval] Approval disabled; proceeding to generation")
            return {"steps": [_step("human_approval", "Approval not required; proceeding")]}

        company = state.get("company") or {}
        selected = state.get("selected_document") or {}
        summary = (
            f"{company.get('symbol', '?')} · "
            f"{selected.get('source_table', 'no document')} "
            f"(year={selected.get('year')}) · "
            f"{len(state.get('requested_kpis') or [])} KPI(s) across "
            f"{len(state.get('requested_categories') or {})} categor(ies)"
        )
        # Pauses here; resumes when the service invokes with Command(resume=...).
        logger.info("[kpi:human_approval] PAUSE awaiting approval — %s", summary)
        decision = interrupt(
            {
                "summary": summary,
                "company": company,
                "selected_document": selected,
                "requested_kpis": state.get("requested_kpis"),
            }
        )
        logger.info("[kpi:human_approval] RESUMED with decision=%r", decision)

        if isinstance(decision, dict):
            verdict = (decision.get("decision") or "").lower()
            feedback = decision.get("feedback")
        else:
            verdict = str(decision).lower()
            feedback = None

        if verdict == "reject":
            logger.info("[kpi:human_approval] DONE rejected by reviewer (feedback=%r)", feedback)
            return {
                "status": "denied",
                "message_out": feedback or "KPI generation was rejected by the reviewer.",
                "steps": [_step("human_approval", "Rejected by reviewer")],
            }
        logger.info("[kpi:human_approval] DONE approved by reviewer")
        return {"steps": [_step("human_approval", "Approved by reviewer")]}

    # --- 10. generate_kpis --------------------------------------------------

    def generate_kpis(self, state: KpiState) -> dict:
        prompt = state.get("kpi_prompt") or ""
        logger.info("[kpi:generate_kpis] START calling LLM (prompt=%d chars)", len(prompt))
        logger.info("Generated Prompts : " + str(prompt) )
        try:
            raw = self.llm.complete(self.prompt_template, prompt)
        except Exception as exc:  # noqa: BLE001 — surfaced as a clean error status
            logger.exception("[kpi:generate_kpis] LLM call failed")
            return {
                "status": "error",
                "message_out": f"KPI generation failed: {exc}",
                "steps": [_step("generate_kpis", "LLM call failed")],
            }
        logger.info("[kpi:generate_kpis] Generated raw response : " + str(raw) )
        logger.info("[kpi:generate_kpis] LLM raw response (%d chars): %.500s", len(raw or ""), raw)
        kpis = _clean_markdown(raw)
        if not kpis:
            # Non-empty raw that cleans to nothing means the model emitted only a
            # (likely truncated/unclosed) <think> block — it ran out of output
            # budget before producing the report.
            truncated_reasoning = bool(raw and raw.strip())
            if truncated_reasoning:
                logger.warning(
                    "[kpi:generate_kpis] DONE response was reasoning-only (%d chars) — "
                    "likely hit the output token limit before emitting the report",
                    len(raw),
                )
                message = (
                    "The model ran out of output space while reasoning and did not "
                    "produce a report. Try a narrower request or raise the model's "
                    "output token limit."
                )
            else:
                logger.warning("[kpi:generate_kpis] DONE empty response from model")
                message = "The model returned an empty KPI report."
            return {
                "status": "error",
                "message_out": message,
                "steps": [_step("generate_kpis", "Model produced no report")],
            }
        logger.info("[kpi:generate_kpis] DONE generated KPI Markdown report (%d chars)", len(kpis))
        return {
            "kpis": kpis,
            "status": "completed",
            "message_out": "KPI analysis complete.",
            "steps": [_step("generate_kpis", "Generated KPI Markdown report")],
        }

    # --- 11. persist --------------------------------------------------------

    def persist(self, state: KpiState) -> dict:
        turn = [
            {"role": "user", "content": state["message"]},
            {
                "role": "assistant",
                "content": state.get("message_out") or "",
                "kpis": state.get("kpis"),
            },
        ]
        logger.info(
            "[kpi:persist] DONE saved turn to history (status=%s)", state.get("status")
        )
        return {
            "messages": turn,
            "steps": [_step("persist", "Saved turn to chat history")],
        }


def _clean_markdown(raw: str) -> str | None:
    """Normalize an LLM response into a clean Markdown report string.

    The model is instructed to emit Markdown only, but reasoning models prefix a
    `<think>...</think>` block and some wrap the whole answer in a ```markdown
    code fence. Strip both so the response renders as plain Markdown.
    """
    if not raw:
        return None
    text = raw.strip()
    # Drop reasoning blocks (closed or trailing-unclosed).
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^<think>.*$", "", text, flags=re.DOTALL).strip()
    # Unwrap a single outer ```markdown ... ``` / ``` ... ``` fence if present.
    fence = re.match(r"^```(?:markdown|md)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    return text or None


def _parse_json(raw: str) -> dict | None:
    """Best-effort extraction of a JSON object from an LLM response.

    Honors the prompt's JSON-only contract but tolerates accidental code fences
    or surrounding prose before giving up.
    """
    if not raw:
        return None
    text = raw.strip()
    # Reasoning models emit a <think>...</think> block before the JSON. Drop it
    # (closed or trailing-unclosed) so its prose/braces don't corrupt extraction.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^<think>.*$", "", text, flags=re.DOTALL).strip()
    # Strip ```json ... ``` fences if the model added them.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


# --- routing -----------------------------------------------------------------


def _after_guardrail(state: KpiState) -> str:
    nxt = END if state.get("status") == "denied" else "resolve_company"
    logger.debug("[kpi:route] finance_guardrail -> %s", nxt)
    return nxt


def _after_resolve(state: KpiState) -> str:
    nxt = END if state.get("status") == "error" else "authorize"
    logger.debug("[kpi:route] resolve_company -> %s", nxt)
    return nxt


def _after_authorize(state: KpiState) -> str:
    nxt = "fetch_documents" if state.get("authorized") else END
    logger.debug("[kpi:route] authorize -> %s", nxt)
    return nxt


def _after_approval(state: KpiState) -> str:
    nxt = END if state.get("status") == "denied" else "generate_kpis"
    logger.debug("[kpi:route] human_approval -> %s", nxt)
    return nxt


def build_kpi_graph(
    nodes: KpiNodes,
    checkpointer: BaseCheckpointSaver,
):
    """Wire the nodes into a compiled, checkpointed StateGraph."""
    graph = StateGraph(KpiState)

    graph.add_node("finance_guardrail", nodes.finance_guardrail)
    graph.add_node("resolve_company", nodes.resolve_company)
    graph.add_node("authorize", nodes.authorize)
    graph.add_node("fetch_documents", nodes.fetch_documents)
    graph.add_node("retrieve_document", nodes.retrieve_document)
    graph.add_node("parse_document", nodes.parse_document)
    graph.add_node("map_kpis", nodes.map_kpis)
    graph.add_node("build_prompt", nodes.build_prompt)
    graph.add_node("human_approval", nodes.human_approval)
    graph.add_node("generate_kpis", nodes.generate_kpis)
    graph.add_node("persist", nodes.persist)

    graph.add_edge(START, "finance_guardrail")
    graph.add_conditional_edges("finance_guardrail", _after_guardrail, ["resolve_company", END])
    graph.add_conditional_edges("resolve_company", _after_resolve, ["authorize", END])
    graph.add_conditional_edges("authorize", _after_authorize, ["fetch_documents", END])
    graph.add_edge("fetch_documents", "retrieve_document")
    graph.add_edge("retrieve_document", "parse_document")
    graph.add_edge("parse_document", "map_kpis")
    graph.add_edge("map_kpis", "build_prompt")
    graph.add_edge("build_prompt", "human_approval")
    graph.add_conditional_edges("human_approval", _after_approval, ["generate_kpis", END])
    graph.add_edge("generate_kpis", "persist")
    graph.add_edge("persist", END)

    return graph.compile(checkpointer=checkpointer)