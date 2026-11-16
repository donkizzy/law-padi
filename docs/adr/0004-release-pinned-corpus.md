# 0004. Publish the corpus as immutable releases and pin conversations to them

Status: accepted. Composite releases added 20 October 2026.

## Context

Legal text is corrected after review, new laws are added, and embeddings are
rebuilt. A saved link or an earlier answer must keep pointing at the wording it
cited, and readers must never see half of a change.

## Decision

- Readers see only a published `CorpusRelease`: a frozen set of provision
  versions with its own validated retrieval index. Releases are not edited in
  place; a correction is a new release.
- Each instrument is ingested and reviewed as its own release, and a composite
  release (`backend/app/ingestion/composition.py`) combines approved members
  with their provenance, rejecting unverified sources, open blocking issues and
  conflicting versions.
- A `Conversation` stores the release and index build it started on, and all of
  its answers are prepared against them.
- Public reads accept `release_version`, so bookmarks and shared links can name
  the edition they were made on.
- Production releases are copied from the reviewed local database and then
  activated; activating the previous release is the rollback
  (`deployment/publish_release.py`).

## Consequences

- Publication and rollback are atomic and cheap.
- Older releases stay in the database while conversations or bookmarks may
  reference them, so storage grows with each release.
- Review evidence (runs, candidates, decisions) stays in the local database
  where the review happened; production receives only the published release.
