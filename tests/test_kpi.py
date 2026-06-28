"""Tests for the KPI agentic workflow (graph + service) with mocked seams.

No live DB, LLM, or storage: the repository, LLM, and storage are mocked, and the
graph runs against an in-memory checkpointer.
"""

from unittest.mock import MagicMock

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.core.interfaces import BaseLLM
from app.core.kpi_repository import DocumentRef
from app.kpi.graph import (
    DENIAL_MESSAGE,
    NON_FINANCE_MESSAGE,
    KpiNodes,
    build_kpi_graph,
)

# The prompt_template passed to KpiNodes in _service(); used to distinguish the
# KPI-generation LLM call from the finance-guardrail call in the mocks.
KPI_PROMPT_TEMPLATE = "KPI SYSTEM PROMPT"
from app.kpi.registry import KpiRegistry
from app.kpi.service import KPIService

KPI_MARKDOWN = """# Tata Consultancy Services — KPI Analysis

**Fiscal Year:** 2024
**Reporting Currency:** INR

## Financial Fields

| Field | Value |
| --- | --- |
| net_profit | 42000 |

## KPIs

### Profitability

| KPI | Value |
| --- | --- |
| net_profit_margin | 25 |
"""


@pytest.fixture()
def registry() -> KpiRegistry:
    return KpiRegistry(
        categories={
            "Profitability KPIs": ["Gross Profit", "Net Profit Margin", "EBITDA"],
            "Return Ratios": ["Return on Equity (ROE)", "Return on Assets (ROA)"],
            "Liquidity KPIs": ["Current Ratio", "Quick Ratio"],
        }
    )


@pytest.fixture()
def repo() -> MagicMock:
    r = MagicMock()
    r.get_user_by_email.return_value = {"id": 1, "email": "a@firm.com", "role": "analyst"}
    r.find_company.return_value = [
        {"id": 7, "symbol": "TCS", "company_name": "Tata Consultancy Services"}
    ]
    r.list_company.return_value = [
        {"id": 7, "symbol": "TCS", "company_name": "Tata Consultancy Services"}
    ]
    r.is_user_authorized.return_value = True
    r.find_company_documents.return_value = [
        DocumentRef(
            source_table="annual_reports",
            document_id=11,
            company_id=7,
            document_type="annual_report",
            title="Annual Report",
            year="2024",
            storage_id="file://abc123",
            filename="abc123.pdf",
            extra={},
        )
    ]
    return r


@pytest.fixture()
def storage() -> MagicMock:
    s = MagicMock()
    s.retrieve.return_value = b"%PDF fake annual report bytes"
    return s


@pytest.fixture()
def llm() -> MagicMock:
    m = MagicMock(spec=BaseLLM)

    def fake_complete(system: str, user: str) -> str:
        if system == KPI_PROMPT_TEMPLATE:
            return KPI_MARKDOWN
        return "YES"  # finance guardrail -> finance-related

    m.complete.side_effect = fake_complete
    return m


def _service(repo, llm, storage, registry, *, require_approval=True, admin_bypass=False):
    nodes = KpiNodes(
        repository=repo,
        llm=llm,
        storage=storage,
        registry=registry,
        prompt_template=KPI_PROMPT_TEMPLATE,
        require_approval=require_approval,
        admin_bypass=admin_bypass,
    )
    graph = build_kpi_graph(nodes, MemorySaver())
    return KPIService(graph)


@pytest.fixture(autouse=True)
def _fake_parser(monkeypatch):
    """Make get_parser return a parser that yields plain text for any filename."""
    parser = MagicMock()
    parser.parse.return_value = "Annual report text. Revenue 100. Net profit 42."
    monkeypatch.setattr("app.kpi.graph.get_parser", lambda name: parser)
    return parser


class TestFinanceGuardrail:
    def test_non_finance_message_denied(self, repo, llm, storage, registry):
        # Classifier says the message is not finance-related → halt before resolve.
        llm.complete.side_effect = lambda system, user: "NO"
        service = _service(repo, llm, storage, registry, require_approval=False)

        result = service.chat("a@firm.com", "TCS", "Tell me a joke", session_id="nf")

        assert result.status == "denied"
        assert result.message == NON_FINANCE_MESSAGE
        repo.find_company.assert_not_called()
        repo.is_user_authorized.assert_not_called()


class TestGuardrail:
    def test_denied_when_not_on_watchlist(self, repo, llm, storage, registry):
        repo.is_user_authorized.return_value = False
        service = _service(repo, llm, storage, registry)

        result = service.chat("a@firm.com", "TCS", "KPIs for TCS", session_id="s1")

        assert result.status == "denied"
        assert result.message == DENIAL_MESSAGE
        # Fail-closed: no document fetch, no storage access, no KPI generation.
        repo.find_company_documents.assert_not_called()
        storage.retrieve.assert_not_called()
        # The KPI generation prompt is never reached.
        assert all(call.args[0] != KPI_PROMPT_TEMPLATE for call in llm.complete.call_args_list)

    def test_denied_when_user_unknown(self, repo, llm, storage, registry):
        repo.get_user_by_email.return_value = None
        service = _service(repo, llm, storage, registry)

        result = service.chat("ghost@firm.com", "TCS", "KPIs for TCS")

        assert result.status == "denied"
        storage.retrieve.assert_not_called()

    def test_admin_bypass(self, repo, llm, storage, registry):
        repo.get_user_by_email.return_value = {"id": 2, "email": "boss@firm.com", "role": "admin"}
        repo.is_user_authorized.return_value = False
        service = _service(repo, llm, storage, registry, require_approval=False, admin_bypass=True)

        result = service.chat("boss@firm.com", "TCS", "Profitability for TCS")

        assert result.status == "completed"
        repo.is_user_authorized.assert_not_called()


class TestHappyPath:
    def test_completed_without_approval(self, repo, llm, storage, registry):
        service = _service(repo, llm, storage, registry, require_approval=False)

        result = service.chat("a@firm.com", "TCS", "Show me TCS profitability ratios", session_id="s1")

        assert result.status == "completed"
        assert result.kpis == KPI_MARKDOWN.strip()
        assert result.company["symbol"] == "TCS"
        storage.retrieve.assert_called_once()
        assert any(s["node"] == "generate_kpis" for s in result.steps)

    def test_unresolvable_company(self, repo, llm, storage, registry):
        # Symbol does not match any company row → cannot resolve.
        repo.find_company.return_value = []
        service = _service(repo, llm, storage, registry, require_approval=False)

        result = service.chat("a@firm.com", "XYZ", "What's the weather", session_id="s1")

        assert result.status == "error"
        repo.is_user_authorized.assert_not_called()


class TestHumanInTheLoop:
    def test_pause_then_approve(self, repo, llm, storage, registry):
        service = _service(repo, llm, storage, registry, require_approval=True)

        first = service.chat("a@firm.com", "TCS", "TCS profitability FY2024", session_id="hitl")
        assert first.status == "awaiting_approval"
        assert first.pending_approval is not None
        assert "TCS" in (first.pending_approval["summary"] or "")

        resumed = service.resume(
            "a@firm.com", "hitl", first.pending_approval["interrupt_id"], "approve"
        )
        assert resumed.status == "completed"
        assert resumed.kpis == KPI_MARKDOWN.strip()

    def test_pause_then_reject(self, repo, llm, storage, registry):
        service = _service(repo, llm, storage, registry, require_approval=True)

        first = service.chat("a@firm.com", "TCS", "TCS profitability", session_id="rej")
        assert first.status == "awaiting_approval"

        resumed = service.resume(
            "a@firm.com", "rej", first.pending_approval["interrupt_id"], "reject", feedback="stop"
        )
        assert resumed.status == "denied"
        assert resumed.kpis is None


class TestMarkdownOutput:
    def test_empty_llm_output_errors(self, repo, llm, storage, registry):
        def blank(system, user):
            if system == KPI_PROMPT_TEMPLATE:
                return "   "
            return "YES"

        llm.complete.side_effect = blank
        service = _service(repo, llm, storage, registry, require_approval=False)

        result = service.chat("a@firm.com", "TCS", "TCS profitability", session_id="bad")

        assert result.status == "error"
        assert "empty" in (result.message or "").lower()

    def test_think_block_and_fence_are_stripped(self, repo, llm, storage, registry):
        def noisy(system, user):
            if system == KPI_PROMPT_TEMPLATE:
                return "<think>computing KPIs...</think>\n```markdown\n" + KPI_MARKDOWN + "\n```"
            return "YES"

        llm.complete.side_effect = noisy
        service = _service(repo, llm, storage, registry, require_approval=False)

        result = service.chat("a@firm.com", "TCS", "TCS profitability", session_id="fence")

        assert result.status == "completed"
        assert result.kpis == KPI_MARKDOWN.strip()


class TestApiRoutes:
    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        from app.api.dependencies import get_kpi_service
        from app.kpi.service import KpiResult
        from app.main import app

        fake = MagicMock()
        fake.chat.return_value = KpiResult(
            session_id="default",
            status="awaiting_approval",
            company={"id": 7, "symbol": "TCS", "company_name": "Tata Consultancy Services"},
            message="TCS · annual_reports (year=2024) · 5 KPI(s)",
            pending_approval={"interrupt_id": "i-1", "summary": "TCS summary"},
            steps=[{"node": "resolve_company", "summary": "Resolved TCS"}],
            took_ms=12.0,
        )
        fake.resume.return_value = KpiResult(
            session_id="default", status="completed", kpis=KPI_MARKDOWN.strip(), took_ms=8.0
        )

        app.dependency_overrides[get_kpi_service] = lambda: fake
        with TestClient(app, raise_server_exceptions=False) as c:
            c._fake = fake
            yield c
        app.dependency_overrides.clear()

    def test_chat_route(self, client):
        resp = client.post(
            "/api/v1/kpi/chat",
            data={"email": "a@firm.com", "symbol": "TCS", "message": "TCS profitability"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "awaiting_approval"
        assert body["company"]["symbol"] == "TCS"
        assert body["pending_approval"]["interrupt_id"] == "i-1"

    def test_chat_route_requires_symbol_and_message(self, client):
        resp = client.post("/api/v1/kpi/chat", data={"email": "a@firm.com"})
        assert resp.status_code == 422

    def test_approve_route(self, client):
        resp = client.post(
            "/api/v1/kpi/approve",
            json={
                "email": "a@firm.com",
                "session_id": "default",
                "interrupt_id": "i-1",
                "decision": "approve",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        client._fake.resume.assert_called_once()


class TestChatMemory:
    def test_followup_reuses_company(self, repo, llm, storage, registry):
        service = _service(repo, llm, storage, registry, require_approval=False)

        first = service.chat("a@firm.com", "TCS", "TCS profitability", session_id="mem")
        assert first.status == "completed"

        # Follow-up omits the symbol entirely; the company is reused from memory
        # (no LLM extraction — resolve_company is symbol-or-memory only).
        second = service.chat("a@firm.com", "", "now add liquidity ratios", session_id="mem")

        assert second.status == "completed"
        assert second.company["symbol"] == "TCS"