# Phase 3: composite release support

The composition API, admin action, indexing path and publication checks are implemented. An approved synthetic Constitution and two synthetic Acts successfully compose, reuse vectors, validate and promote in the dedicated test database. The existing conversation keeps its original release and index; a new conversation uses the composite.

**Actual local activation remains blocked by Phase 2 acceptance.** ACJA 2015 and Police Act 2020 are still `needs_review`, have no materialised versions and have no approved member releases. The Phase 2 OCR and numbering defects remain open. No composite containing these Acts was created or promoted in the application database. The active Constitution release remains `draft-c8d50d87fae9`. [Local preflight evidence](statute-phase3-local-preflight-2026-10-19.json).

## Compose and review

In Legal admin → Corpus releases, **Compose release** shows the production Constitution base and approved releases containing one Act. A corpus publisher supplies a unique release version and selects the Act releases. Unapproved releases remain outside the selection. Accounts without publisher access have disabled controls. The existing project design tokens and squircle controls are preserved.

The API is `POST /api/v1/admin/corpus-releases/compose`. Its request includes `idempotency_key`, `version`, `base_release_id`, `expected_base_version`, and `members` containing each `release_id` and `expected_version`. It returns a `CorpusReleasePublic`; its validation report identifies the composition run. Release responses now include `instrument_slugs` and `instrument_types`. The client was regenerated with the repository script.

Composition queues retrieval-document construction and pauses at **Ready to embed**. The admin then uses the existing run action to start embedding and indexing, validates the resulting release, and publishes through the existing publisher/uploader separation flow. Composition itself does not approve sources or publish a release. Actual use of this path requires completing the source and extraction reviews first.

## Membership and integrity

The new release copies the union of member entries while preserving every original source ID, provision-version ID and ingestion-run ID. It records member release IDs and versions, entry snapshot hashes, source hashes, parser versions and edition notices. The manifest also retains canonical text hashes, legal status and source-page locations, and supplies all source cards to the existing manifest panel.

The composer rejects stale versions, an inactive base, non-Act additions, missing canonical provenance, unverified sources, incomplete Act materialisation, unapproved candidates, open blocking issues, conflicting versions of one provision and canonical text/hash mismatches. It uses one database transaction for release, entries, run, tasks, audit and idempotency records. Concurrent requests serialize on the production base; exact retries reuse their result.

Member manifests and the copied union are rechecked before retrieval construction, embedding, indexing, release validation and publication. A changed member, changed source hash, conflicting provenance or retired base blocks a pending composite. Retiring the base during successful publication remains valid for the published composite and existing pinned conversations.

Original ingestion runs continue to identify their original release after their entries are copied. The composite build has an explicit release identity and reaches `published` after successful activation.

## Indexing and vector reuse

Pgvector reuse requires identical retrieval text and a matching pinned embedding-profile fingerprint, including provider, model, revision, dimensions and configuration. Only selected successful runs with ready/promoted validated builds from frozen members qualify. The worker verifies retained artifact hashes, original vector checksums and equality with PostgreSQL's float32 representation. Reused vectors are written under the new release's own segments and embedding run; member data is unchanged.

Changed inputs, a changed profile, missing provenance or missing artifacts fall back to embedding. Corrupt retained evidence fails the run. Older runs without a profile fingerprint also fall back. Benchmark query vectors are generated and the composite benchmark runs before model selection. Qdrant follows the existing embedding path without this reuse optimisation. No paid embedding calls were made for the real Acts during implementation.

The regression exposed and fixed a lexical smoke check that failed for citations containing only a stopword and a one-digit number, such as “Section 9”. It also fixed retirement/promotion ordering under the single-production constraint. Retirement is flushed within the same transaction before promotion, so UUID update order cannot violate the unique index.

## Validation

Backend validation: **561 passed, 4 skipped**, including **18 composition cases**, with **89%** coverage. Mypy, ty, Ruff lint/format, frontend build and Biome passed. Browser regressions: **36 passed**, with no retry needed. [Validation summary](statute-phase3-validation-2026-10-19.json). The source acceptance failures from Phase 2 remain separate prerequisites; the two optional real-PDF checks are skipped in the ordinary suite and were not recertified in this phase.

The Constitution retrieval report is identical to Phase 2 across all 97 cases: 57-case hit@1/hit@5 **0.98/1.00** and held-out 40-case **0.95/1.00**. Its active index still validates with **1,829 segments and 1,829 embeddings**, and unchanged segment and embedding checksums. [Retrieval comparison](statute-phase3-retrieval-validation-2026-10-19.json).

Desktop and mobile browser evidence used synthetic fixtures. The generated screenshots were inspected and later removed at the user's request on 20 October 2026. These were interface checks, not evidence that either real Act is approved.

The plan's completion criterion—an actual composite in local production—has not been reached. Complete the Phase 2 OCR correction, full-PDF checks, source verification and extraction approval before composing the real corpus. Phases 4–7 remain future work.
