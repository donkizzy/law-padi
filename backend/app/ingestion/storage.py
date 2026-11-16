from pathlib import Path
from typing import cast

from app.core.config import settings
from app.ingestion.blob_store import (
    BlobStoreError,
    LocalBlobStore,
)
from app.ingestion.contracts import (
    BlobStore,
)
from app.ingestion.r2_blob_store import R2BlobStore


def get_blob_store() -> BlobStore:
    if settings.INGESTION_STORAGE_BACKEND == "r2":
        missing = [
            name
            for name, value in {
                "R2_ENDPOINT_URL": settings.R2_ENDPOINT_URL,
                "R2_BUCKET_NAME": settings.R2_BUCKET_NAME,
                "R2_ACCESS_KEY_ID": settings.R2_ACCESS_KEY_ID,
                "R2_SECRET_ACCESS_KEY": settings.R2_SECRET_ACCESS_KEY,
            }.items()
            if not value
        ]
        if missing:
            raise BlobStoreError(
                f"R2 storage is missing required settings: {', '.join(missing)}"
            )
        return R2BlobStore(
            endpoint_url=cast(str, settings.R2_ENDPOINT_URL),
            bucket_name=cast(str, settings.R2_BUCKET_NAME),
            access_key_id=cast(str, settings.R2_ACCESS_KEY_ID),
            secret_access_key=cast(str, settings.R2_SECRET_ACCESS_KEY),
        )
    return LocalBlobStore(Path(settings.INGESTION_STORAGE_DIR))
