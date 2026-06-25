import json
import os
import uuid
from pathlib import PurePosixPath
from urllib.parse import urlparse

import boto3
import requests
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

from .storage import DataStorage

load_dotenv()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

RAG_API_BASE_URL = os.environ.get("RAG_API_BASE_URL", "http://localhost:8080")
INGEST_FILE_URL = f"{RAG_API_BASE_URL}/api/v1/ingest/file"

STORAGE_ID_PREFIX = "s3://"


class AwsFileStorage(DataStorage):
    """Stores the content fetched from a URL as an object in an Amazon S3 bucket.

    All AWS configuration is read from environment variables (see .env.example):
      - AWS_S3_BUCKET           target bucket name (required)
      - AWS_REGION              bucket region, e.g. ap-south-1
      - AWS_S3_PREFIX           optional key prefix applied to every object
      - AWS_ACCESS_KEY_ID       optional; falls back to the default boto3
      - AWS_SECRET_ACCESS_KEY   credential chain (IAM role, profile, etc.)
      - AWS_SESSION_TOKEN       optional, for temporary credentials
      - AWS_S3_ENDPOINT_URL     optional, for S3-compatible stores (MinIO/LocalStack)
    """

    def __init__(
        self,
        bucket_name: str | None = None,
        region_name: str | None = None,
        prefix: str | None = None,
    ):
        self.bucket_name = bucket_name or os.environ.get("AWS_S3_BUCKET")
        if not self.bucket_name:
            raise ValueError("AWS_S3_BUCKET must be set to use AwsFileStorage")

        self.region_name = region_name or os.environ.get("AWS_REGION")
        self.prefix = (prefix if prefix is not None else os.environ.get("AWS_S3_PREFIX", "")).strip("/")

        self.client = boto3.client(
            "s3",
            region_name=self.region_name,
            endpoint_url=os.environ.get("AWS_S3_ENDPOINT_URL") or None,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID") or None,
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY") or None,
            aws_session_token=os.environ.get("AWS_SESSION_TOKEN") or None,
            config=Config(retries={"max_attempts": 3, "mode": "standard"}),
        )

    def store(self, url: str, bucket: str | None, json_obj: dict | None = None) -> str:
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()

            file_id = uuid.uuid4().hex
            suffix = PurePosixPath(urlparse(url).path).suffix
            key = self._build_key(bucket, f"{file_id}{suffix}")

            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=response.content,
                Metadata=self._build_metadata(json_obj),
            )

            #self._ingest_file(f"{file_id}{suffix}", response.content, json_obj)

            return STORAGE_ID_PREFIX + key
        except (requests.RequestException, BotoCoreError, ClientError):
            return "FILE_NOT_FOUND"

    def retrieve(self, storage_id: str, bucket: str | None = None) -> bytes:
        key = storage_id.removeprefix(STORAGE_ID_PREFIX)
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()
        except (BotoCoreError, ClientError) as exc:
            raise FileNotFoundError(
                f"No stored content for storage id {storage_id!r} in bucket {self.bucket_name!r}"
            ) from exc

    def _build_key(self, bucket: str | None, filename: str) -> str:
        parts = [part for part in (self.prefix, bucket, filename) if part]
        return "/".join(parts)

    @staticmethod
    def _build_metadata(json_obj: dict | None) -> dict:
        """S3 object metadata values must be strings; skip None values."""
        if not json_obj:
            return {}
        return {k: str(v) for k, v in json_obj.items() if v is not None}

    def _ingest_file(self, filename: str, content: bytes, json_obj: dict | None) -> None:
        """Forward the downloaded document and its record to the RAG ingest API."""
        files = [("files", (filename, content, "application/octet-stream"))]
        data = {"metadata": json.dumps(json_obj)} if json_obj is not None else None
        response = requests.post(INGEST_FILE_URL, files=files, data=data, timeout=60)
        response.raise_for_status()