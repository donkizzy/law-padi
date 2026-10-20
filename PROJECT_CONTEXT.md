# Law Padi Project Context

This file preserves the key project context from the shared ChatGPT export:

- Share URL: https://chatgpt.com/share/6a94523e-e5f4-83ea-ae0e-083703c4f103
- Export title: `Branch - Architect Nigerian Constitution RAG`
- Local pasted export: `/Users/amosgodwin/.codex/attachments/8952f6d1-38b4-483f-9815-58fd9d12a1ba/pasted-text.txt`

The export is product and architecture context. Do not treat legal-status statements in it as authoritative without checking official sources again.

## Current implementation and rollout state (2026-10-09)

- Multi-instrument infrastructure (2026-10-20): references and canonical evidence are instrument-scoped; Constitution citation strings are preserved. Migrations `f5a6b7c8d9e0` and `a7b8c9d0e1f2` support retrieval instrument identity and upload type. Act parsing and ingestion are opt-in, force historical/as-enacted materialisation, and require arrangement/body reconciliation. The admin composite-release action freezes approved member provenance, queues an independent retrieval build, reuses eligible pgvector embeddings, and applies source/review gates to every member. Synthetic composition/promotion and conversation pinning are tested. Actual ACJA 2015 and Police Act 2020 sources remain `needs_review`, with failing OCR/numbering acceptance checks and no materialised versions. Neither Act is published. Phases 4–5 add qualified retrieval, prompt `constitution-english-v11`, instrument-aware citation validation, canonical application/supremacy context and per-law notices. Synthetic multi-law answer contracts pass, while all 97 Constitution retrieval results remain unchanged. The Police Act expected count is corrected to 142 from its retained arrangement. Phase 6 adds a release-scoped instruments endpoint, law picker, filtered Browse/Find, canonical `/laws/<slug>/…` routes with legacy Constitution aliases, law-aware source/saved/export presentation and public metadata/sitemaps. Only the Constitution appears in the actual public law list. Actual composite activation, live statute evaluation and Phase 7 remain pending. See `docs/statute-ingestion-progress-2026-10-19.md`, `docs/statute-phase3-composite-release-2026-10-19.md`, `docs/statute-phase5-answer-generation-2026-10-20.md` and `docs/statute-phase6-frontend-2026-10-20.md`.
- PostgreSQL stores canonical provisions, immutable release entries, retrieval segments, 1,024-dimensional pgvector embeddings, and the active retrieval target. Qdrant is not the deployed retrieval backend. The published `draft-c8d50d87fae9` edition is historical/source Constitution wording, not certified current consolidated law.
- Exact citation lookup and semantic search share `backend/app/legal/evidence.py`. Exact lookup supports section/subsection/paragraph references, lists, and bounded ranges, and loads targeted canonical versions without an embedding provider. Semantic candidates are release-scoped and reloaded with targeted canonical reads; embedding failure has a disclosed lexical fallback.
- `backend/app/api/routes/conversations.py` and `backend/app/chat/` implement release-pinned guest/account conversations, explicit guest claiming, idempotent submissions, run-scoped replayable SSE events, durable workers, a DeepSeek JSON adapter, two-stage answer validation, and Lagos-day spend reservations. Reservations survive conversation deletion for later charge reconciliation. Follow-ups can reuse a single resolved identity and carry the preceding question into the explanation. The API and worker run separately. The generation feature flags default off pending evaluation and provider-capacity approval.
- The frontend has a chat entry point, paginated history, source cards, and a provision explanation action that preserves the selected version identity. Existing Browse and Saved flows remain available. The current extension is English-only; the multilingual product vision below is future scope.
- An accidental run of the old destructive test fixture against the local `app` database cleared its corpus and account/review records. The public release was rebuilt from the retained original PDF, release manifest, retrieval documents, and embedding checkpoints. All 1,811 legal-text hashes and 1,829 vector checksums matched retained review evidence; the active index passed live validation. The bootstrap superuser was recreated. Prior account and review history was not recoverable from these artifacts. An ignored safety dump is at `backend/storage/backups/app-recovered-2026-10-07.dump`.
- Plain-language retrieval and answers (2026-10-12): `backend/app/legal/topics.py` maps everyday and Pidgin-style phrasing to sections and adds them as a weighted list to RRF fusion alongside dense and keyword search; keyword search now ORs content words instead of requiring every word. Section and chapter titles come from the source PDF's "Arrangement of sections" (`backend/app/legal/data/constitution-1999-section-titles.json`) and are exposed as `title` on results and evidence. Prompt `constitution-english-v7` answers the question first in plain English, adds companion limits (for example Section 45 for Sections 37–41), returns follow-up questions, and never mentions AI, "stored wording" or the edition; one edition caveat is shown by the UI instead. Later blocks that fail deterministic or verifier checks are dropped; a failing first block still rejects the answer. `docs/plain-language-retrieval-benchmark-v1.json` measured 82% → 98% top-1 section hits.
- Pytest now rejects non-`_test` database names; `backend/scripts/test.sh` provisions and migrates a dedicated companion test database. The versioned 200-case English explanation set is in `docs/constitution-explanation-evaluation-v1.json`. Its deterministic checks pass, and a controlled isolated 1,000-generation/SSE load test passed. The bounded live-case collector and offline human-review page are ready. The DeepSeek key is configured locally. A single capped live case reached generation and verification but was withheld by grounding validation. The probe also exposed a normalized-versus-served-text hash mismatch in evidence cards; the evidence boundary now supplies the exact served-text hash and verifies the stored canonical hash. Provider quota confirmation, a successful live probe, 200 live captures, and human grounding review remain pending. See `docs/evidence-chat-rollout.md`.

## Product Vision

Law Padi is a web-based Nigerian constitutional law assistant. People should be able to ask natural chat-style questions about the Constitution of the Federal Republic of Nigeria, including exact references, incomplete references, and broad concepts.

Example questions:

- "What does Section 37 say?"
- "Which part of the Constitution covers freedom of speech?"
- "What section talks about privacy?"
- "wetin constitution talk about police checking my phone?"
- "section thirty something about privacy"

The assistant should respond with:

- a clear plain-language explanation;
- the exact constitutional provision when available;
- precise legal citation generated by the backend;
- official English wording where relevant;
- current, historical, or proposed-law status;
- amendment history where relevant;
- links or references to authoritative source documents;
- a clear distinction between current constitutional law and proposed constitutional amendments.

Supported user-facing languages should include English, Nigerian Pidgin, Igbo, Yoruba, and Hausa. Official constitutional wording remains English. Translations of official wording must be labeled as accessibility translations, not authoritative legal text.

## Core Architecture Decisions

- Use the existing FastAPI full-stack template as scaffolding, then reshape it around the legal domain.
- Keep a modular monolith in one repository, with multiple runtime processes when needed.
- PostgreSQL is the legal source of truth.
- Qdrant is retrieval infrastructure, not the legal source of truth.
- LLMs explain law from verified evidence; they never decide what the law is.
- The evidence layer is a product boundary: every answer should be traceable to exact stored provisions and source documents.
- Current law, historical law, and proposed amendments must be modeled and displayed separately.
- Do not model a bill or proposed amendment as current law.
- Generate citations server-side from structured metadata, not from model text.
- Heavy ML dependencies should live outside the main API package, likely in an indexer/worker container, because the backend currently targets Python `>=3.14`.

## Resolved V1 Decisions

- Remove the template `Item` feature rather than repurposing it.
- Support anonymous conversations from day one.
- Include Constitution/provisions, amendments, and bills in the first legal schema.
- Keep source-document storage metadata in the schema, but leave the actual storage backend for a later setup.

## Current Repository Baseline

This repository is still close to the FastAPI full-stack template:

- Backend: FastAPI, Pydantic, SQLModel, PostgreSQL, Alembic.
- Frontend: React, Vite, Tailwind, shadcn/ui, TanStack Router/Query, generated OpenAPI client.
- Tests: Pytest for backend, Playwright for frontend.
- Infrastructure: Docker Compose with PostgreSQL, backend, Traefik, Adminer, and Mailpit-related local setup.
- Current backend keeps the template `User` auth model, while legal-domain tables live under `backend/app/legal/`.
- Alembic imports `SQLModel.metadata` from `backend/app/models.py` in `backend/app/alembic/env.py`.

## Implemented Foundation (2026-08-30)

- The template `Item` feature is removed from the backend API, SQLModel metadata, generated OpenAPI client, frontend route tree, UI components, and browser tests. Historical Alembic migrations still mention `item` because migration history is immutable; the new migration drops that table.
- The first legal schema is implemented in `backend/app/legal/models.py` and `backend/app/legal/enums.py`.
- Alembic revision `7f4d9c2a1b6e` creates the legal tables and adds PostgreSQL `btree_gist` validity-range enforcement for provision versions.
- Anonymous conversations are represented by `conversation.anonymous_session_id`; authenticated conversations use `conversation.user_id`. The database requires at least one owner value.
- Source blobs are intentionally not configured yet. `source_document.storage_key` is nullable until the object-storage decision is made.
- To create or update the local schema after starting PostgreSQL, run `cd backend && uv run alembic upgrade head`. The repository bootstrap uses `cd backend && uv run bash scripts/prestart.sh` to migrate and seed the initial user.
- The schema foundation does not yet implement chat, retrieval, ingestion, or public legal API routes; those remain the next application-layer milestones.

## Target Backend Shape

Evolve the backend toward domain modules without prematurely splitting into many microservices:

```text
backend/app/
  api/routes/
    chat.py
    search.py
    provisions.py
    amendments.py
    bills.py
    feedback.py
    admin/
      sources.py
      ingestion.py
      reviews.py
      corpus.py
      evaluation.py
  legal/
    enums.py
    models.py
    schemas.py
    repositories.py
    citations/
    amendments/
    versions/
  retrieval/
    exact.py
    semantic.py
    lexical.py
    fusion.py
    reranker.py
    service.py
  languages/
    detector.py
    normalizer.py
    translator.py
    terminology.py
  llm/
    client.py
    providers/
    prompts/
    answerer.py
  chat/
    models.py
    schemas.py
    service.py
  evaluation/
    runner.py
    metrics.py
    datasets.py
```

Separate runtime support can later live under:

```text
services/indexer/
  worker.py
  fetch.py
  extract.py
  parse.py
  embed.py
  publish.py
  jobs.py
```

## Schema Design Principles

Divide the data model into these areas:

- Legal corpus
- Legislative lifecycle
- Chat and evidence
- Ingestion, audit, and corpus releases
- Legal terminology and evaluation

The most important modeling distinction is provision identity versus provision text:

- `Provision` is the stable identity, such as "Section 37".
- `ProvisionVersion` is what that provision said during a specific legal-validity period.

This allows the product to answer questions like:

- What does Section 37 say today?
- What did Section 37 say before an amendment?
- Which amendment created the current wording?

## Target Legal Tables

### `legal_instrument`

Represents constitutions, alteration acts, bills, acts, and later regulations.

Important fields:

- `id`
- `slug`
- `title`
- `short_title`
- `instrument_type`
- `jurisdiction`
- `year`
- `status`
- `enacted_at`
- `effective_at`
- `ceased_at`
- `created_at`
- `updated_at`

### `source_document`

Represents immutable official or trusted source artifacts.

Important fields:

- `id`
- `legal_instrument_id`
- `authority`
- `title`
- `source_url`
- `mime_type`
- `sha256`
- `storage_key`
- `published_at`
- `retrieved_at`
- `source_tier`
- `parser_version`
- `extraction_method`
- `verification_status`
- `verified_by`
- `verified_at`

Original source files should be stored immutably in object storage. Never overwrite a source document blob.

### `provision`

Represents a structural legal identity.

Important fields:

- `id`
- `instrument_id`
- `parent_id`
- `kind`
- `number`
- `heading`
- `canonical_path`
- `sort_key`

Example canonical paths:

- `constitution.1999.chapter4.section37`
- `constitution.1999.chapter4.section37.subsection1`

### `provision_version`

Represents text valid during a legal period.

Important fields:

- `id`
- `provision_id`
- `text`
- `normalized_text`
- `valid_from`
- `valid_until`
- `legal_status`
- `revision_number`
- `source_document_id`
- `source_page_start`
- `source_page_end`
- `text_sha256`
- `created_by_amendment_id`
- `supersedes_id`
- `created_at`

PostgreSQL should enforce non-overlapping validity ranges for the same `provision_id`.

### `amendment`

Represents a constitutional alteration instrument.

Important fields:

- `id`
- `instrument_id`
- `title`
- `act_number`
- `year`
- `status`
- `passed_at`
- `effective_at`
- `source_document_id`

### `amendment_operation`

Represents a reviewed patch-like operation against legal text.

Important fields:

- `id`
- `amendment_id`
- `target_provision_id`
- `target_version_id`
- `operation_type`
- `selector`
- `old_text`
- `new_text`
- `old_text_hash`
- `sort_order`
- `review_status`
- `reviewed_by`
- `reviewed_at`

Amendment operations should behave like patches. If `old_text_hash` does not match the current provision text hash, the operation must stop for manual review.

### `constitutional_bill`

Represents proposed constitutional changes without treating them as law.

Important fields:

- `id`
- `instrument_id`
- `bill_number`
- `title`
- `introduced_at`
- `originating_chamber`
- `status`
- `current_stage`
- `last_verified_at`

### `legislative_event`

Represents the immutable timeline of a bill.

Important fields:

- `id`
- `bill_id`
- `event_type`
- `event_date`
- `chamber`
- `description`
- `source_document_id`
- `source_url`
- `verified_at`

### `conversation`

Represents a user or anonymous chat thread.

Important fields:

- `id`
- `user_id`
- `anonymous_session_id`
- `title`
- `preferred_language`
- `created_at`
- `updated_at`

### `message`

Represents a user or assistant message.

Important fields:

- `id`
- `conversation_id`
- `role`
- `content`
- `detected_language`
- `created_at`
- `answer_status`
- `model_provider`
- `model_name`
- `retrieval_trace_id`

### `message_evidence`

Connects assistant messages to the exact legal evidence used.

Important fields:

- `id`
- `message_id`
- `provision_version_id`
- `evidence_role`
- `retrieval_rank`
- `retrieval_score`
- `citation_label`

Evidence roles:

- `primary`
- `supporting`
- `background`

### `legal_concept`

Represents curated legal topics used for retrieval and explainability.

Important fields:

- `id`
- `slug`
- `canonical_name`
- `description`

Examples: privacy, freedom-expression, property-rights, citizenship, legislative-power, presidential-qualification.

### `legal_concept_alias`

Represents reviewed multilingual or colloquial phrases that map to legal concepts.

Important fields:

- `id`
- `concept_id`
- `language`
- `phrase`
- `normalized_phrase`
- `weight`
- `reviewed`

### `corpus_release`

Represents a validated, promotable corpus and retrieval-index release.

Important fields:

- `id`
- `version`
- `status`
- `created_at`
- `approved_at`
- `approved_by`
- `source_manifest_hash`
- `embedding_model`
- `embedding_model_version`
- `parser_version`

Release statuses can include `building`, `validating`, `approved`, `production`, and `retired`.

## Recommended Schema Creation Path

Use SQLModel first, with Alembic migrations for PostgreSQL-specific constraints.

1. Keep the existing auth/user models working while adding legal-domain models.
2. Create `backend/app/legal/enums.py` for domain enums.
3. Create `backend/app/legal/models.py` for legal corpus, amendment, bill, chat-evidence, terminology, ingestion, and release tables.
4. Import `backend/app/legal/models.py` from `backend/app/models.py`, or update `backend/app/alembic/env.py` so Alembic imports every table model before reading `SQLModel.metadata`.
5. Keep API request/response schemas separate in `backend/app/legal/schemas.py`; do not put public API-only fields on table models.
6. Use `Column(Text)` or SQLModel `sa_column` for long legal text fields.
7. Use PostgreSQL `JSONB` for selectors, parser metadata, retrieval traces, and flexible review details.
8. Generate an Alembic revision from the backend directory:

```bash
uv run alembic revision --autogenerate -m "add legal corpus schema"
```

9. Hand-review the generated migration. Autogenerate will not produce every legal integrity rule correctly.
10. Add PostgreSQL-specific migration operations manually:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;
```

Add an exclusion constraint so one provision cannot have two overlapping versions:

```sql
ALTER TABLE provision_version
ADD CONSTRAINT provision_version_no_overlap
EXCLUDE USING gist (
  provision_id WITH =,
  daterange(valid_from, COALESCE(valid_until, 'infinity'::date), '[)') WITH &&
);
```

11. Add normal indexes and uniqueness constraints for:

- `legal_instrument.slug`
- `provision.canonical_path`
- `provision.instrument_id`
- `provision.parent_id`
- `provision_version.provision_id`
- `provision_version.text_sha256`
- `source_document.sha256`
- `constitutional_bill.status`
- `conversation.user_id`
- `message.conversation_id`

12. Apply the migration:

```bash
uv run alembic upgrade head
```

13. Add tests before building retrieval:

- table metadata imports without errors;
- a provision can have one current version;
- overlapping provision versions are rejected by PostgreSQL;
- a bill can exist without becoming current law;
- a message can link to exact evidence;
- source document hashes are unique;
- amendment operation hash mismatch is rejected in application logic.

## First Implementation Milestones

Build the legal foundation before polishing chat:

1. Add the legal schema.
2. Ingest one clean authoritative Constitution source document.
3. Parse deterministic hierarchy: chapter, part, section, subsection, paragraph, schedule item.
4. Implement exact citation lookup before semantic retrieval.
5. Implement amendment/version application and review flow.
6. Add Qdrant with separate collections for enacted law and proposals.
7. Add hybrid retrieval: exact reference lookup, dense multilingual retrieval, sparse legal retrieval, curated aliases, RRF fusion, then reranking.
8. Create about 200 golden evaluation questions across exact references, incomplete references, semantic questions, typos, historical questions, proposed amendments, and supported Nigerian languages.
9. Add answer generation only after retrieval and citation validation are measurable.
10. Build the polished chat UI.

## Qdrant and Retrieval Notes

Separate enacted law from proposals:

```text
ng_constitution_enacted_r0001
ng_constitution_proposals_r0001
```

Expose stable aliases:

```text
constitution_enacted
constitution_proposals
```

Use legal structural units as retrieval points, not arbitrary fixed-size chunks:

- section;
- subsection;
- paragraph;
- schedule item.

Initial vector setup:

- `dense_multilingual`
- `sparse_legal`

Later benchmark late-interaction or ColBERT-style reranking, but do not start there.

Retrieval should run these paths in parallel where possible:

- exact citation/reference parser;
- dense search in the original language;
- query translation to English;
- dense search in English;
- sparse legal search;
- curated terminology and aliases.

Fuse results with RRF first, then tune weighted RRF after evaluations exist.

## API Shape

Likely public API routes:

```text
POST   /api/v1/conversations
GET    /api/v1/conversations
GET    /api/v1/conversations/{id}
DELETE /api/v1/conversations/{id}
POST   /api/v1/conversations/{id}/messages
POST   /api/v1/conversations/{id}/messages:stream

GET    /api/v1/search
GET    /api/v1/provisions/{id}
GET    /api/v1/provisions/by-citation
GET    /api/v1/provisions/{id}/history
GET    /api/v1/provisions/{id}/versions/{version}
GET    /api/v1/provisions/{id}/amendments

GET    /api/v1/amendments
GET    /api/v1/amendments/{id}
GET    /api/v1/amendments/{id}/operations

GET    /api/v1/bills
GET    /api/v1/bills/{id}
GET    /api/v1/bills/{id}/timeline

POST   /api/v1/messages/{id}/feedback
```

Use SSE for streaming chat responses. Expected events:

- `message.started`
- `retrieval.started`
- `retrieval.complete`
- `answer.delta`
- `citation`
- `answer.complete`
- `error`

## UI Direction

The chat is the product. Do not make a dashboard with a chatbot attached.

Desktop layout:

- left conversation/navigation sidebar;
- dominant center chat;
- optional right legal source context panel that only opens when useful.

Mobile layout:

- compact top bar;
- no permanent desktop sidebar;
- navigation in a drawer or sheet;
- citations open source context in a bottom sheet or full-screen sheet.

Design style:

- calm, trustworthy, contemporary, premium;
- not a government portal;
- not a traditional legal database;
- not a flashy AI product;
- subtle deep emerald primary accent;
- amber for proposed-law status;
- neutral for historical/superseded law;
- color never carries legal meaning alone.

Every radius-based UI element should use a centralized squircle primitive or squircle design token. Do not scatter arbitrary `rounded-*` classes through the frontend.

## Remaining Questions Before Ingestion

- Which source should be the first authoritative Constitution document for ingestion?
- Which fields must be admin-editable versus ingestion-only?
- Do we need row-level access rules for saved conversations at the database level in V1?
- Should corpus releases be required before any provision becomes visible, or can V1 expose a manually seeded draft corpus?

## Implemented Public Retrieval Integration (6 October 2026)

Home, Browse, Provision Detail, and browser-local Saved now use the published corpus under `/api/v1/legal`. Exact section/subsection/paragraph references resolve against stored release entries independently of embedding providers. Topic searches reuse the saved pgvector index and return ranked choices; provider failures disclose a lexical fallback. Wording and complete citations are loaded from canonical versions and ancestry. Original PDF access, parent context, children, stored published history, copy/share, and release-pinned bookmarks are integrated.

Public reads require an active production target or an explicitly selected previously published release. Drafts remain private. The active local release `draft-c8d50d87fae9` was verified as production, with the historical LFN 2004 source-edition label. No publication state, corpus wording, indexed text, or corpus embeddings were changed. Section 168 remains missing and the two Section 189 identities remain distinguishable by source location.

As of 19 October 2026, instrument-scoped references, canonical evidence identity and citations support multiple instruments. Act ingestion is opt-in through `INGESTION_ALLOWED_INSTRUMENT_TYPES` (default Constitution only). The Act parser and per-instrument title catalogues preserve source identities and require arrangement/body reconciliation. Act materialisation forces historical/as-enacted semantics. ACJA 2015 and Police Act 2020 scans are registered and staged for private extraction review, with source verification and OCR correction still pending. Both full-PDF acceptance checks currently fail; no Act canonical versions or public release entries exist. Phase 2 acceptance and the composite-release phase remain incomplete. See [the statute implementation and review report](docs/statute-ingestion-progress-2026-10-19.md).

English retrieval and browser bookmarks were the preceding milestone. The evidence-backed chat extension now implements persistent conversations and gated AI explanations, with generation disabled until the evaluation and capacity gates pass. Translations, account-synced bookmarks, and proposed-change ingestion remain later milestones. See [the integration report](docs/public-corpus-integration.md) for prior API behavior and [the chat rollout guide](docs/evidence-chat-rollout.md) for current controls and validation status.


As of 20 October 2026, Phase 6 exposes published instruments through `/api/v1/legal/instruments`, scopes tree and Find searches by instrument, and uses `/laws/<slug>/…` canonical reading URLs. Legacy `/constitution` URLs and release-pinned bookmarks remain usable. Per-law citations, source editions, saved/export URLs, landing copy and server-rendered sitemap/metadata are implemented; the site retains the constitution.ng design system. Synthetic multi-law browser fixtures are presentation tests only. The actual picker still contains only the historical Constitution, and the two Act sources remain unverified, unmaterialised and unpublished. See [Phase 6](docs/statute-phase6-frontend-2026-10-20.md) for validation and remaining review gates.


Post-review corrections (20 October 2026): source references are extracted independently, with source-relative `this Act` handling and preservation of Section 45 context. New section markers reset to the supplied default law; unknown ACJL qualifiers are rejected and “Nigerian Police Act” is recognised. Mixed releases no longer cap Constitution results at three, and first-place promotion requires a matched query topic inside the requested result window. All 97 Constitution cases retain aggregate fused/fallback scores in a disposable mixed-law test database. Public Act titles can fall back to stored arrangement headings, but full title catalogues, source verification and OCR acceptance remain pending. Phone-search phrasing now includes release-gated Act topic hints. The real Acts remain unpublished. See [review fixes and validation](docs/statute-review-fixes-2026-10-20.md).
