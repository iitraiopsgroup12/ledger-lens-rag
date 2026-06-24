import logging

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.core.interfaces import BaseChunker

logger = logging.getLogger(__name__)


class RecursiveChunker(BaseChunker):
    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split(self, text: str, metadata: dict) -> list[Document]:
        return self._splitter.create_documents([text], metadatas=[metadata])


class InvoiceChunker(BaseChunker):
    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 50) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

    def split(self, text: str, metadata: dict) -> list[Document]:
        return self._splitter.create_documents([text], metadatas=[metadata])


class FinancialReportChunker(BaseChunker):
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

    def split(self, text: str, metadata: dict) -> list[Document]:
        return self._splitter.create_documents([text], metadatas=[metadata])


class LegalChunker(BaseChunker):
    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 300) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "Section", "Article", "\n", " "],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split(self, text: str, metadata: dict) -> list[Document]:
        return self._splitter.create_documents([text], metadatas=[metadata])


class TabularChunker(BaseChunker):
    def __init__(self, chunk_size: int = 300, chunk_overlap: int = 0) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            separators=["\n"],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split(self, text: str, metadata: dict) -> list[Document]:
        return self._splitter.create_documents([text], metadatas=[metadata])


class MarkdownChunker(BaseChunker):
    _HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4")]

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 100) -> None:
        self._chunk_size = chunk_size
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self._HEADERS,
            strip_headers=False,
        )
        self._fallback = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

    def split(self, text: str, metadata: dict) -> list[Document]:
        header_chunks = self._header_splitter.split_text(text)
        result: list[Document] = []
        for hchunk in header_chunks:
            combined_meta = {**metadata, **hchunk.metadata}
            if len(hchunk.page_content) <= self._chunk_size:
                result.append(Document(page_content=hchunk.page_content, metadata=combined_meta))
            else:
                sub = self._fallback.create_documents(
                    [hchunk.page_content], metadatas=[combined_meta]
                )
                result.extend(sub)
        if not result:
            return self._fallback.create_documents([text], metadatas=[metadata])
        return result


class AdaptiveChunker(BaseChunker):
    def __init__(
        self,
        invoice_chunk_size: int = 400,
        invoice_chunk_overlap: int = 50,
        financial_chunk_size: int = 800,
        financial_chunk_overlap: int = 150,
        legal_chunk_size: int = 1500,
        legal_chunk_overlap: int = 300,
        tabular_chunk_size: int = 300,
        tabular_chunk_overlap: int = 0,
        markdown_chunk_size: int = 1000,
        markdown_chunk_overlap: int = 100,
        narrative_chunk_size: int = 1000,
        narrative_chunk_overlap: int = 200,
    ) -> None:
        from app.core.document_classifier import DocumentClassifier, DocumentType

        self._classifier = DocumentClassifier()
        self._chunkers: dict = {
            DocumentType.INVOICE: InvoiceChunker(invoice_chunk_size, invoice_chunk_overlap),
            DocumentType.FINANCIAL_REPORT: FinancialReportChunker(financial_chunk_size, financial_chunk_overlap),
            DocumentType.LEGAL: LegalChunker(legal_chunk_size, legal_chunk_overlap),
            DocumentType.TABULAR: TabularChunker(tabular_chunk_size, tabular_chunk_overlap),
            DocumentType.MARKDOWN: MarkdownChunker(markdown_chunk_size, markdown_chunk_overlap),
            DocumentType.NARRATIVE: RecursiveChunker(narrative_chunk_size, narrative_chunk_overlap),
        }

    def split(self, text: str, metadata: dict) -> list[Document]:
        doc_type = self._classifier.classify(text, metadata)
        chunks = self._chunkers[doc_type].split(text, metadata)
        for chunk in chunks:
            chunk.metadata["doc_type"] = doc_type.value
        logger.info(
            "AdaptiveChunker classified %d chars as %s → %d chunk(s)",
            len(text),
            doc_type.value,
            len(chunks),
        )
        return chunks
