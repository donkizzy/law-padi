import json
import threading
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.blob_store import LocalBlobStore
from app.ingestion.extraction import NativePdfExtractor
from app.ingestion.pdf import profile_pdf_pages
from app.ingestion.r2_blob_store import R2BlobStore
from app.ingestion.rendering import RenderedPageThumbnail, render_page_thumbnail
from app.ingestion.runtime.queue import enqueue_task
from app.ingestion.runtime.runner import run_once, run_until_idle
from app.ingestion.stages.page_payloads import raw_extraction_payloads
from app.legal.enums import (
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionTaskStatus,
    PageInclusionStatus,
)
from app.legal.models import IngestionArtifact, IngestionRun, SourcePage
from tests.factories.pdf import pdf_with_pages
from tests.ingestion.worker.conftest import _stored_source_and_run


def test_source_is_streamed_once_and_reused_across_stages(
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    _source, run = _stored_source_and_run(
        db,
        tmp_path=tmp_path,
        pdf=pdf_with_pages([f"1. Law {uuid.uuid4().hex}", "2. Law"]),
    )
    original_read = LocalBlobStore.read_bytes
    original_iter = LocalBlobStore.iter_read
    downloads: list[str] = []
    rendered_paths: list[Path] = []

    def read(store: LocalBlobStore, key: str) -> bytes:
        assert not key.startswith("sources/"), "source must be streamed"
        return original_read(store, key)

    def chunks(store: LocalBlobStore, key: str) -> Any:
        if key.startswith("sources/"):
            downloads.append(key)
        return original_iter(store, key)

    def render(
        content: Any, *, page_number: int, **_kwargs: Any
    ) -> RenderedPageThumbnail:
        assert isinstance(content, Path)
        assert content.exists()
        rendered_paths.append(content)
        return RenderedPageThumbnail(page_number, b"png")

    monkeypatch.setattr(LocalBlobStore, "read_bytes", read)
    monkeypatch.setattr(LocalBlobStore, "iter_read", chunks)
    monkeypatch.setattr("app.ingestion.stages.pages.render_page_thumbnail", render)
    run_until_idle(db, worker_id="streaming", max_tasks=5)
    db.refresh(run)
    assert run.status == IngestionRunStatus.WAITING_FOR_INPUT
    assert len(downloads) == 1
    assert len(rendered_paths) == 2
    assert rendered_paths[0] == rendered_paths[1]
    assert not rendered_paths[0].exists()
    for page in db.exec(select(SourcePage).where(SourcePage.run_id == run.id)).all():
        page.inclusion_status = PageInclusionStatus.INCLUDED
        db.add(page)
    db.commit()

    def forbid_extraction(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("native extraction must reuse profiling text and spans")

    monkeypatch.setattr(NativePdfExtractor, "iter_extract", forbid_extraction)
    enqueue_task(
        db,
        run=run,
        step=None,
        task_type=IngestionStage.NATIVE_EXTRACTION.value,
        idempotency_key=f"{run.id}:native-reuse",
        payload={},
    )
    result = run_once(db, worker_id="streaming", task_type="native_extraction")
    assert result is not None and result.task_status == IngestionTaskStatus.SUCCEEDED
    assert len(downloads) == 1


def test_pdf_tools_accept_source_path_without_copying_pdf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = pdf_with_pages(["1. Law"])
    path = tmp_path / "source.pdf"
    path.write_bytes(content)
    assert (
        profile_pdf_pages(path, max_pages=10)[0].extracted_text
        == profile_pdf_pages(content, max_pages=10)[0].extracted_text
    )
    assert (
        NativePdfExtractor().extract(path)[0].text
        == NativePdfExtractor().extract(content)[0].text
    )
    write = Path.write_bytes

    def guard(path: Path, data: bytes) -> int:
        assert not data.startswith(b"%PDF"), "renderer must reuse the existing PDF path"
        return write(path, data)

    monkeypatch.setattr(Path, "write_bytes", guard)
    assert render_page_thumbnail(path, page_number=1).content.startswith(b"\x89PNG")


def test_r2_open_read_uses_bounded_stream_instead_of_read_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = b"x" * (2 * 1024 * 1024)
    store = R2BlobStore(
        endpoint_url="https://test",
        bucket_name="test",
        access_key_id="test",
        secret_access_key="test",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, content=content)
            )
        ),
    )

    def forbid(_key: str) -> bytes:
        raise AssertionError("buffered download")

    monkeypatch.setattr(store, "read_bytes", forbid)
    with store.open_read("source") as stream:
        assert stream.read(10) == b"x" * 10
        assert stream.seek(0, 2) == len(content)


def test_page_artifacts_are_fetched_concurrently_with_one_store(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = IngestionRun()
    db.add(run)
    db.commit()
    for number in range(1, 4):
        db.add(
            IngestionArtifact(
                run_id=run.id,
                artifact_type=IngestionArtifactType.RAW_EXTRACTION,
                storage_key=f"parallel/{number}",
                artifact_metadata={"page_number": number},
            )
        )
    db.commit()
    barrier = threading.Barrier(3)
    factories: list[None] = []

    class Store:
        def read_bytes(self, key: str) -> bytes:
            barrier.wait(timeout=5)
            return json.dumps(
                {"page_number": int(key.rsplit("/", 1)[1]), "text": key}
            ).encode()

    store = Store()

    def factory() -> Store:
        factories.append(None)
        return store

    monkeypatch.setattr("app.ingestion.stages.page_payloads.get_blob_store", factory)
    assert [payload["page_number"] for payload in raw_extraction_payloads(db, run)] == [
        1,
        2,
        3,
    ]
    assert len(factories) == 1


def test_native_text_and_spans_are_extracted_once_for_profiling_and_selection(
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdf._page import PageObject

    from app.ingestion.stages.pages import handle_native_extraction, handle_profiling
    from app.legal.models import IngestionTask

    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    _source, run = _stored_source_and_run(
        db, tmp_path=tmp_path, pdf=pdf_with_pages([f"1. Law {uuid.uuid4().hex}"])
    )
    task = db.exec(select(IngestionTask).where(IngestionTask.run_id == run.id)).one()
    extract = PageObject.extract_text
    calls: list[None] = []

    def count(page: PageObject, *args: Any, **kwargs: Any) -> str:
        calls.append(None)
        return extract(page, *args, **kwargs)

    monkeypatch.setattr(PageObject, "extract_text", count)
    handle_profiling(db, run, task)
    page = db.exec(select(SourcePage).where(SourcePage.run_id == run.id)).one()
    page.inclusion_status = PageInclusionStatus.INCLUDED
    db.add(page)
    db.commit()
    handle_native_extraction(db, run, task)
    assert len(calls) == 2


def test_source_cache_evicts_old_files_within_its_disk_budget(
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ingestion.runtime.source_files import SourceFileCache

    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    first, _ = _stored_source_and_run(
        db, tmp_path=tmp_path, pdf=pdf_with_pages([uuid.uuid4().hex])
    )
    second, _ = _stored_source_and_run(
        db, tmp_path=tmp_path, pdf=pdf_with_pages([uuid.uuid4().hex])
    )
    root = tmp_path / "cache"
    root.mkdir()
    cache = SourceFileCache(
        root, max_bytes=max(first.file_size or 0, second.file_size or 0) + 1
    )
    first_path = cache.source_path(first)
    second_path = cache.source_path(second)
    assert not first_path.exists()
    assert second_path.exists()
    refreshed = cache.source_path(first)
    assert refreshed.exists()
    assert not second_path.exists()
