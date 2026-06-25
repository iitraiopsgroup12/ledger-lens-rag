"""Storage provider for KPI document retrieval.

A document's `s3_key` (from the documents table) carries a scheme that selects
the backend:
  file://  -> LocalFileStorage
  aws://   -> AwsFileStorage   (s3:// is accepted as an alias)

`RoutingDataStorage` keeps the graph table-agnostic: nodes call
`storage.retrieve(storage_id, bucket)` and the right backend is chosen here.
"""
import logging

from nse_data_storage import AwsFileStorage, DataStorage, LocalFileStorage

logger = logging.getLogger(__name__)

_AWS_PREFIXES = ("aws://", "s3://")


class RoutingDataStorage(DataStorage):
    """Dispatches retrieve()/store() to a concrete backend by storage-id prefix."""

    def __init__(self, local: DataStorage | None = None) -> None:
        self._local = local or LocalFileStorage()
        self._aws: DataStorage | None = None

    def _aws_backend(self) -> DataStorage:
        # Built lazily: AwsFileStorage() requires AWS_* env and should not be
        # constructed unless an aws:// pointer is actually requested.
        if self._aws is None:
            self._aws = AwsFileStorage()
        return self._aws

    def _backend_for(self, storage_id: str) -> DataStorage:
        if (storage_id or "").startswith(_AWS_PREFIXES):
            return self._aws_backend()
        return self._local

    def retrieve(self, storage_id: str, bucket: str | None = None) -> bytes:
        return self._backend_for(storage_id).retrieve(storage_id, bucket)

    def store(self, url: str, bucket: str | None, json_obj: dict | None = None) -> str:
        return self._local.store(url, bucket, json_obj)


def build_document_storage(storage_dir: str | None = None) -> DataStorage:
    """Return the configured DataStorage (default: LocalFileStorage)."""
    logger.info("Building KPI document storage (dir=%s)", storage_dir)
    local = LocalFileStorage(storage_dir) if storage_dir else LocalFileStorage()
    return RoutingDataStorage(local=local)