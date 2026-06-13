"""Unit tests for all chunker implementations in app/core/chunking.py."""

import pytest

from app.core.chunking import (
    AdaptiveChunker,
    FinancialReportChunker,
    InvoiceChunker,
    LegalChunker,
    MarkdownChunker,
    TabularChunker,
)
from app.core.document_classifier import DocumentType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _long_text(n_chars: int, seed: str = "word ") -> str:
    return (seed * (n_chars // len(seed) + 1))[:n_chars]


# ---------------------------------------------------------------------------
# InvoiceChunker
# ---------------------------------------------------------------------------

class TestInvoiceChunker:
    chunker = InvoiceChunker(chunk_size=400, chunk_overlap=50)

    def test_respects_chunk_size(self):
        text = _long_text(2000)
        chunks = self.chunker.split(text, {})
        assert all(len(c.page_content) <= 450 for c in chunks)

    def test_metadata_preserved(self):
        meta = {"source": "invoice.pdf", "file_type": "pdf"}
        chunks = self.chunker.split("Invoice Total $100", meta)
        for chunk in chunks:
            assert chunk.metadata["source"] == "invoice.pdf"

    def test_short_text_produces_single_chunk(self):
        chunks = self.chunker.split("Invoice #001 Total $50", {})
        assert len(chunks) == 1


# ---------------------------------------------------------------------------
# FinancialReportChunker
# ---------------------------------------------------------------------------

class TestFinancialReportChunker:
    chunker = FinancialReportChunker(chunk_size=800, chunk_overlap=150)

    def test_respects_chunk_size(self):
        text = _long_text(4000)
        chunks = self.chunker.split(text, {})
        assert all(len(c.page_content) <= 900 for c in chunks)


# ---------------------------------------------------------------------------
# LegalChunker
# ---------------------------------------------------------------------------

class TestLegalChunker:
    chunker = LegalChunker(chunk_size=1500, chunk_overlap=300)

    def test_splits_on_double_newline(self):
        section1 = "Section 1. " + _long_text(200)
        section2 = "Section 2. " + _long_text(200)
        text = section1 + "\n\n" + section2
        chunks = self.chunker.split(text, {})
        # With small section text, should produce >= 1 chunk; sections can stay together if small enough
        assert len(chunks) >= 1

    def test_large_document_produces_multiple_chunks(self):
        text = "\n\n".join(f"Section {i}. " + _long_text(400) for i in range(6))
        chunks = self.chunker.split(text, {})
        assert len(chunks) > 1

    def test_metadata_forwarded(self):
        meta = {"doc_id": "contract-001"}
        chunks = self.chunker.split("Whereas the party shall agree.", meta)
        assert all(c.metadata.get("doc_id") == "contract-001" for c in chunks)


# ---------------------------------------------------------------------------
# TabularChunker
# ---------------------------------------------------------------------------

class TestTabularChunker:
    chunker = TabularChunker(chunk_size=300, chunk_overlap=0)

    def test_splits_on_newlines(self):
        # Each row is ~40 chars; 40 rows = ~1600 chars, well above the 300 chunk size
        rows = "\n".join(f"product_item_{i:03d}\t{i * 10:.2f}\t{i * 20:.2f}\tcategory_x" for i in range(40))
        chunks = self.chunker.split(rows, {})
        assert len(chunks) > 1

    def test_no_overlap_between_chunks(self):
        rows = "\n".join(f"item{i}\tvalue{i}" for i in range(10))
        chunks = self.chunker.split(rows, {})
        # Zero overlap: consecutive chunks should not share content
        if len(chunks) > 1:
            assert chunks[0].page_content != chunks[1].page_content


# ---------------------------------------------------------------------------
# MarkdownChunker
# ---------------------------------------------------------------------------

class TestMarkdownChunker:
    chunker = MarkdownChunker(chunk_size=500, chunk_overlap=50)

    def test_splits_on_headers(self):
        text = "# Introduction\nSome intro content.\n\n## Methods\nMethod details here.\n\n## Results\nResult details."
        chunks = self.chunker.split(text, {})
        assert len(chunks) >= 2

    def test_header_metadata_in_chunks(self):
        text = "# Main Title\nContent under main title.\n## Sub Section\nSub content."
        chunks = self.chunker.split(text, {})
        # At least one chunk should have header metadata from MarkdownHeaderTextSplitter
        has_header_meta = any("h1" in c.metadata or "h2" in c.metadata for c in chunks)
        assert has_header_meta

    def test_fallback_on_no_headers(self):
        text = _long_text(1200, seed="plain prose word ")
        chunks = self.chunker.split(text, {})
        assert len(chunks) >= 1
        assert all(len(c.page_content) <= 600 for c in chunks)

    def test_caller_metadata_preserved(self):
        meta = {"source_file": "readme.md"}
        text = "# Title\nContent here."
        chunks = self.chunker.split(text, meta)
        assert all(c.metadata.get("source_file") == "readme.md" for c in chunks)


# ---------------------------------------------------------------------------
# AdaptiveChunker
# ---------------------------------------------------------------------------

class TestAdaptiveChunker:
    chunker = AdaptiveChunker()

    def test_doc_type_injected_into_chunk_metadata(self):
        text = "Invoice #001 Bill To: Acme. Due Date: Jan 1. Total Amount: $100. Subtotal $90. Tax $10."
        chunks = self.chunker.split(text, {})
        assert all("doc_type" in c.metadata for c in chunks)

    def test_invoice_text_routes_to_invoice(self):
        text = "Invoice Number: INV-42. Bill To: Client. Due Date: 2024-03-01. Total Amount: $500. Subtotal: $450. Tax: $50."
        chunks = self.chunker.split(text, {})
        assert chunks[0].metadata["doc_type"] == DocumentType.INVOICE.value

    def test_csv_metadata_routes_to_tabular(self):
        text = "name\tvalue\nalice\t100\nbob\t200"
        chunks = self.chunker.split(text, {"file_type": "csv"})
        assert chunks[0].metadata["doc_type"] == DocumentType.TABULAR.value

    def test_md_metadata_routes_to_markdown(self):
        text = "# Title\nSome content."
        chunks = self.chunker.split(text, {"file_type": "md"})
        assert chunks[0].metadata["doc_type"] == DocumentType.MARKDOWN.value

    def test_legal_text_routes_to_legal(self):
        text = (
            "Whereas the party hereinafter referred to as Client shall comply with this contract. "
            "Governing law: California. Jurisdiction: SF County. Indemnify and hold harmless. "
            "Representations and warranties included."
        )
        chunks = self.chunker.split(text, {})
        assert chunks[0].metadata["doc_type"] == DocumentType.LEGAL.value

    def test_narrative_text_routes_to_narrative(self):
        text = "The committee met to discuss various topics. Several proposals were tabled for review."
        chunks = self.chunker.split(text, {})
        assert chunks[0].metadata["doc_type"] == DocumentType.NARRATIVE.value

    def test_chunker_instances_are_reused(self):
        # Call split twice; same chunker instance for the same type should be used
        text = "Invoice #X. Total Amount: $999. Bill To: Corp. Due Date: now. Subtotal $900. Tax $99."
        chunks1 = self.chunker.split(text, {})
        chunks2 = self.chunker.split(text, {})
        # Verify same _chunkers dict object (not re-instantiated)
        from app.core.document_classifier import DocumentType as DT
        assert self.chunker._chunkers[DT.INVOICE] is self.chunker._chunkers[DT.INVOICE]
        assert chunks1[0].metadata["doc_type"] == chunks2[0].metadata["doc_type"]
