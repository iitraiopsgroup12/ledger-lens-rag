from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.interfaces import BaseChunker


class RecursiveChunker(BaseChunker):
    """Chunks text using LangChain's RecursiveCharacterTextSplitter."""

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split(self, text: str, metadata: dict) -> list[Document]:
        return self._splitter.create_documents([text], metadatas=[metadata])
