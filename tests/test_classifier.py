"""Unit tests for DocumentClassifier — no I/O, pure text/metadata inputs."""

import pytest

from app.core.document_classifier import DocumentClassifier, DocumentType


@pytest.fixture()
def clf():
    return DocumentClassifier()


class TestFileTypeShortCircuits:
    def test_csv_returns_tabular(self, clf):
        assert clf.classify("any text", {"file_type": "csv"}) == DocumentType.TABULAR

    def test_xlsx_returns_tabular(self, clf):
        assert clf.classify("any text", {"file_type": "xlsx"}) == DocumentType.TABULAR

    def test_xls_returns_tabular(self, clf):
        assert clf.classify("any text", {"file_type": "xls"}) == DocumentType.TABULAR

    def test_md_returns_markdown(self, clf):
        assert clf.classify("# Title\n\nsome content", {"file_type": "md"}) == DocumentType.MARKDOWN


class TestKeywordDensityScoring:
    def test_invoice_keywords(self, clf):
        text = "Invoice Number: 1234. Bill To: Acme Corp. Due Date: 2024-02-01. Total Amount: $500. Subtotal $450. Tax $50."
        assert clf.classify(text, {}) == DocumentType.INVOICE

    def test_financial_report_keywords(self, clf):
        text = "Revenue for Q3 was $2M. Net income improved. Balance sheet shows equity of $5M. Cash flow positive. Fiscal year results strong."
        assert clf.classify(text, {}) == DocumentType.FINANCIAL_REPORT

    def test_legal_keywords(self, clf):
        text = (
            "Whereas the party hereinafter referred to as Client shall agree to this contract. "
            "Jurisdiction is California. Governing law applies. Indemnify clause included. "
            "Representations and warranties are provided."
        )
        assert clf.classify(text, {}) == DocumentType.LEGAL

    def test_sparse_text_defaults_to_narrative(self, clf):
        text = "The weather was nice today. We went for a walk in the park. It was a pleasant afternoon."
        assert clf.classify(text, {}) == DocumentType.NARRATIVE


class TestStructuralBoosts:
    def test_tab_heavy_text_classifies_tabular(self, clf):
        # 3 tabs per line on average → TABULAR boost
        rows = "\n".join(f"item{i}\t100\t200\t300" for i in range(10))
        result = clf.classify(rows, {})
        assert result == DocumentType.TABULAR

    def test_pipe_heavy_text_classifies_tabular(self, clf):
        rows = "\n".join(f"| col1 | col2 | col3 |" for _ in range(10))
        result = clf.classify(rows, {})
        assert result == DocumentType.TABULAR

    def test_markdown_headings_classify_markdown(self, clf):
        text = "# Title\n## Section One\nSome content here.\n## Section Two\nMore content.\n### Subsection\nDetails."
        result = clf.classify(text, {})
        assert result == DocumentType.MARKDOWN


class TestEdgeCases:
    def test_invoice_beats_weak_financial_signal(self, clf):
        # Mostly invoice keywords, one financial word — invoice should win
        text = "Invoice Number: INV-001. Bill To: Customer. Due Date: Jan 1. Total Amount: $300. Revenue noted."
        result = clf.classify(text, {})
        assert result == DocumentType.INVOICE

    def test_no_file_type_in_metadata_uses_content(self, clf):
        text = "This Agreement is entered by the Parties. Whereas the party hereinafter shall comply. Governing law: NY. Indemnify the client."
        result = clf.classify(text, {})
        assert result == DocumentType.LEGAL

    def test_empty_metadata_does_not_crash(self, clf):
        result = clf.classify("hello world", {})
        assert result == DocumentType.NARRATIVE

    def test_empty_text_does_not_crash(self, clf):
        result = clf.classify("", {})
        assert result == DocumentType.NARRATIVE
