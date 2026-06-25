import json
import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from .storage import DataStorage

load_dotenv()

DEFAULT_STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", "storage"))
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

RAG_API_BASE_URL = os.environ.get("RAG_API_BASE_URL", "http://localhost:8080")
INGEST_FILE_URL = f"{RAG_API_BASE_URL}/api/v1/ingest/file"


class LocalFileStorage(DataStorage):
    """Stores the content fetched from a URL as a file on the local filesystem."""

    def __init__(self, storage_dir: Path | str = DEFAULT_STORAGE_DIR):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def store(self, url: str, bucket: str | None, json_obj: dict | None = None) -> str:
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()

            target_dir = self.storage_dir
            if bucket is not None:
                target_dir = target_dir / bucket
                target_dir.mkdir(parents=True, exist_ok=True)

            file_id = uuid.uuid4().hex
            suffix = Path(urlparse(url).path).suffix
            file_path = target_dir / f"{file_id}{suffix}"
            file_path.write_bytes(response.content)

            #self._ingest_file(file_path.name, response.content, json_obj)

            return "file://" + file_id
        except:
            return "FILE_NOT_FOUND"

    def retrieve(self, storage_id: str, bucket: str | None = None) -> bytes:
        file_id = storage_id.removeprefix("file://")

        target_dir = self.storage_dir
        if bucket is not None:
            target_dir = target_dir / bucket

        matches = list(target_dir.glob(f"{file_id}.*")) + list(target_dir.glob(file_id))
        if not matches:
            raise FileNotFoundError(
                f"No stored content for storage id {storage_id!r} in bucket {bucket!r}"
            )

        return matches[0].read_bytes()

    def _ingest_file(self, filename: str, content: bytes, json_obj: dict | None) -> None:
        """Forward the downloaded document and its record to the RAG ingest API."""
        files = [("files", (filename, content, "application/octet-stream"))]
        data = {"metadata": json.dumps(json_obj)} if json_obj is not None else None
        response = requests.post(INGEST_FILE_URL, files=files, data=data, timeout=60)
        response.raise_for_status()