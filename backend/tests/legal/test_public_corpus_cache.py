"""The shared public corpus: what is kept, what is loaded, and who waits."""

import threading
from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.legal import public_corpus
from app.legal.enums import CorpusReleaseStatus, LegalStatus, ProvisionKind
from app.legal.models import (
    CorpusRelease,
    CorpusReleaseEntry,
    Provision,
    ProvisionVersion,
)
from app.legal.parser import legal_text_sha256
from app.legal.public_corpus import (
    PublicCorpus,
    cached_public_corpus,
    derive_public_corpus,
    load_public_corpus,
    wait_for_corpus_refreshes,
)


def _copy_release(db: Session, release: CorpusRelease, version: str) -> CorpusRelease:
    copy = CorpusRelease(version=version, status=CorpusReleaseStatus.RETIRED)
    db.add(copy)
    db.flush()
    for entry in db.exec(
        select(CorpusReleaseEntry).where(CorpusReleaseEntry.release_id == release.id)
    ).all():
        db.add(
            CorpusReleaseEntry(
                release_id=copy.id,
                provision_version_id=entry.provision_version_id,
                source_document_id=entry.source_document_id,
            )
        )
    db.commit()
    return copy


def _counted_loads(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    loads: list[tuple[str, str]] = []

    def counted(session, release, *, index_kind="enacted"):
        loads.append((release.version, threading.current_thread().name))
        return load_public_corpus(session, release, index_kind=index_kind)

    monkeypatch.setattr(public_corpus, "load_public_corpus", counted)
    return loads


def test_reading_older_releases_keeps_the_production_corpus(
    client: TestClient, corpus, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    release, _source, nodes, _pdf = corpus
    older = [_copy_release(db, release, f"older-{index}") for index in range(3)]
    loads = _counted_loads(monkeypatch)
    path = f"/api/v1/legal/provisions/{nodes['chapter4.section37'].canonical_path}"
    for _ in range(2):
        for item in older:
            response = client.get(path, params={"release_version": item.version})
            assert response.status_code == 200
            assert response.json()["data"][0]["release_version"] == item.version
        assert client.get(path).json()["data"][0]["release_version"] == (
            release.version
        )
    # Older releases are built from the production rows, never loaded whole,
    # and reading them neither evicts nor reloads production.
    assert [version for version, _thread in loads] == [release.version]


def test_derived_corpus_matches_a_full_load(corpus, db: Session) -> None:
    release, source, nodes, _pdf = corpus
    older = _copy_release(db, release, "older")
    section = nodes["chapter4.section37"]
    current = db.exec(
        select(ProvisionVersion).where(ProvisionVersion.provision_id == section.id)
    ).one()
    earlier_text = "Earlier wording of section 37."
    earlier = ProvisionVersion(
        provision_id=section.id,
        source_document_id=source.id,
        text=earlier_text,
        normalized_text=earlier_text,
        text_sha256=legal_text_sha256(earlier_text),
        legal_status=LegalStatus.HISTORICAL,
        valid_from=date(1979, 1, 1),
        valid_until=current.valid_from,
        revision_number=current.revision_number + 1,
    )
    # A chapter and section that only the older release publishes.
    chapter = Provision(
        instrument_id=section.instrument_id,
        kind=ProvisionKind.CHAPTER,
        number="9",
        canonical_path="constitution-1999.chapter9",
        sort_key="0900",
    )
    db.add_all([earlier, chapter])
    db.flush()
    repealed = Provision(
        instrument_id=section.instrument_id,
        parent_id=chapter.id,
        kind=ProvisionKind.SECTION,
        number="300",
        canonical_path="constitution-1999.chapter9.section300",
        sort_key="0901",
    )
    db.add(repealed)
    db.flush()
    repealed_text = "A section only the older release has."
    repealed_version = ProvisionVersion(
        provision_id=repealed.id,
        source_document_id=source.id,
        text=repealed_text,
        normalized_text=repealed_text,
        text_sha256=legal_text_sha256(repealed_text),
        legal_status=LegalStatus.HISTORICAL,
        valid_from=date(1979, 1, 1),
    )
    db.add(repealed_version)
    db.flush()
    entry = db.exec(
        select(CorpusReleaseEntry).where(
            CorpusReleaseEntry.release_id == older.id,
            CorpusReleaseEntry.provision_version_id == current.id,
        )
    ).one()
    entry.provision_version_id = earlier.id
    db.add(entry)
    db.add(
        CorpusReleaseEntry(
            release_id=older.id,
            provision_version_id=repealed_version.id,
            source_document_id=source.id,
        )
    )
    db.commit()

    base = load_public_corpus(db, release)
    for index_kind in ("enacted", "proposals"):
        full = load_public_corpus(db, older, index_kind=index_kind)
        derived = derive_public_corpus(db, older, base, index_kind=index_kind)
        assert derived is not None
        assert {pid: v.id for pid, v in derived.versions.items()} == {
            pid: v.id for pid, v in full.versions.items()
        }
        assert derived.provisions.keys() == full.provisions.keys()
        assert derived.sources.keys() == full.sources.keys()
        assert derived.instruments.keys() == full.instruments.keys()
    derived = derive_public_corpus(db, older, base)
    assert derived is not None
    assert derived.versions[section.id].id == earlier.id
    assert base.versions[section.id].id == current.id
    assert {repealed.id, chapter.id} <= derived.provisions.keys()


def _fake_release(index_kind: str, status: CorpusReleaseStatus) -> CorpusRelease:
    return CorpusRelease(id=uuid4(), version=f"fake-{index_kind}", status=status)


def test_a_slow_load_does_not_hold_up_other_releases(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    slow = _fake_release("enacted", CorpusReleaseStatus.PRODUCTION)
    fast = _fake_release("proposals", CorpusReleaseStatus.PRODUCTION)
    started = threading.Event()
    finish = threading.Event()
    loads: list[str] = []

    def load(_session, release, *, index_kind="enacted"):
        loads.append(release.version)
        if release.id == slow.id:
            started.set()
            assert finish.wait(10)
        return PublicCorpus(release, {}, {}, {}, index_kind)

    monkeypatch.setattr(public_corpus, "load_public_corpus", load)
    results: dict[str, PublicCorpus] = {}

    def read(name: str, release: CorpusRelease, index_kind: str) -> None:
        results[name] = cached_public_corpus(db, release, index_kind=index_kind)

    waiting = [
        threading.Thread(target=read, args=(f"slow-{n}", slow, "enacted"))
        for n in range(2)
    ]
    waiting[0].start()
    assert started.wait(5)
    waiting[1].start()
    other = threading.Thread(target=read, args=("fast", fast, "proposals"))
    other.start()
    other.join(5)
    try:
        assert not other.is_alive(), "another release waited for the slow load"
        assert results["fast"].release is fast
    finally:
        finish.set()
        for thread in [*waiting, other]:
            thread.join(10)
    # Both requests for the slow release shared its one load.
    assert loads.count(slow.version) == 1
    assert results["slow-0"].provisions is results["slow-1"].provisions


def test_due_corpus_is_served_while_it_reloads_in_the_background(
    corpus, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    release, _source, _nodes, _pdf = corpus
    loads = _counted_loads(monkeypatch)
    first = cached_public_corpus(db, release)
    key = (release.id, "enacted")
    public_corpus._corpus_cache[key] = replace(
        public_corpus._corpus_cache[key], refresh_at=0
    )
    served = cached_public_corpus(db, release)
    assert served.provisions is first.provisions
    wait_for_corpus_refreshes()
    refreshed = cached_public_corpus(db, release)
    assert refreshed.provisions is not first.provisions
    assert refreshed.provisions.keys() == first.provisions.keys()
    assert [version for version, _thread in loads] == [release.version] * 2
    request_thread, refresh_thread = (thread for _version, thread in loads)
    assert request_thread == threading.current_thread().name
    assert refresh_thread != request_thread


def test_older_releases_are_dropped_least_recently_used(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    production = _fake_release("enacted", CorpusReleaseStatus.PRODUCTION)
    monkeypatch.setattr(
        public_corpus, "published_release", lambda *_a, **_k: production
    )
    monkeypatch.setattr(
        public_corpus,
        "load_public_corpus",
        lambda _session, item, **kwargs: PublicCorpus(item, {}, {}, {}, **kwargs),
    )
    size = public_corpus.RETIRED_CORPUS_CACHE_SIZE
    older = [
        CorpusRelease(
            id=uuid4(), version=f"older-{n}", status=CorpusReleaseStatus.RETIRED
        )
        for n in range(size + 1)
    ]
    cached_public_corpus(db, production)
    for item in older[:size]:
        cached_public_corpus(db, item)
    cached_public_corpus(db, older[0])
    cached_public_corpus(db, older[size])
    cached = [key[0] for key in public_corpus._corpus_cache]
    assert production.id in cached
    assert [release_id for release_id in cached if release_id != production.id] == [
        *(item.id for item in older[2:size]),
        older[0].id,
        older[size].id,
    ]
