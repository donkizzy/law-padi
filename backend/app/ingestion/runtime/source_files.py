import hashlib
import tempfile
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import closing, contextmanager
from functools import wraps
from pathlib import Path
from typing import cast

from sqlmodel import Session

from app.ingestion.runtime.errors import IngestionWorkerError
from app.ingestion.runtime.types import StageHandler, StageOutcome
from app.ingestion.storage import get_blob_store
from app.legal.models import IngestionRun, IngestionTask, SourceDocument

MAX_SOURCE_BYTES = 500 * 1024 * 1024


class SourceFileCache:
    def __init__(self, root: Path, *, max_bytes: int = 512 * 1024 * 1024) -> None:
        self.root = root
        self.max_bytes = max_bytes
        self.files: OrderedDict[str, tuple[Path, int]] = OrderedDict()

    def source_path(self, source: SourceDocument) -> Path:
        key = source.sha256
        if key in self.files:
            self.files.move_to_end(key)
            return self.files[key][0]
        if not source.storage_key:
            raise IngestionWorkerError("Source document does not have a stored file")
        # Reserve enough room for the largest allowed input before downloading.
        expected = source.file_size or MAX_SOURCE_BYTES
        while (
            self.files
            and sum(size for _, size in self.files.values()) + expected > self.max_bytes
        ):
            _, (old_path, _) = self.files.popitem(last=False)
            old_path.unlink(missing_ok=True)
        digest = hashlib.sha256()
        size = 0
        with tempfile.NamedTemporaryFile(
            dir=self.root, suffix=".pdf", delete=False
        ) as temporary:
            path = Path(temporary.name)
            try:
                with closing(get_blob_store().iter_read(source.storage_key)) as chunks:
                    for chunk in chunks:
                        size += len(chunk)
                        if size > min(MAX_SOURCE_BYTES, self.max_bytes):
                            raise IngestionWorkerError(
                                "Stored source exceeds the PDF size limit"
                            )
                        digest.update(chunk)
                        temporary.write(chunk)
                if digest.hexdigest() != source.sha256:
                    raise IngestionWorkerError("Stored source SHA-256 does not match")
                if source.file_size is not None and size != source.file_size:
                    raise IngestionWorkerError("Stored source size does not match")
            except BaseException:
                path.unlink(missing_ok=True)
                raise
        self.files[key] = (path, size)
        return path


@contextmanager
def source_file_cache() -> Iterator[SourceFileCache]:
    with tempfile.TemporaryDirectory(prefix="ingestion-sources-") as root:
        yield SourceFileCache(Path(root))


@contextmanager
def source_files(
    session: Session, cache: SourceFileCache | None = None
) -> Iterator[SourceFileCache]:
    existing = cast(SourceFileCache | None, session.info.get("ingestion_source_cache"))
    if cache is None and existing is not None:
        yield existing
        return
    if cache is None:
        with source_file_cache() as temporary_cache:
            with source_files(session, temporary_cache) as active:
                yield active
        return
    session.info["ingestion_source_cache"] = cache
    try:
        yield cache
    finally:
        if existing is None:
            session.info.pop("ingestion_source_cache", None)
        else:
            session.info["ingestion_source_cache"] = existing


def with_source_files(handler: StageHandler) -> StageHandler:
    @wraps(handler)
    def wrapped(
        session: Session, run: IngestionRun, task: IngestionTask
    ) -> StageOutcome:
        expire = session.expire_on_commit
        session.expire_on_commit = False
        try:
            with source_files(session):
                return handler(session, run, task)
        finally:
            session.expire_on_commit = expire

    return wrapped


def source_path(session: Session, source: SourceDocument) -> Path:
    cache = cast(SourceFileCache, session.info["ingestion_source_cache"])
    return cache.source_path(source)
