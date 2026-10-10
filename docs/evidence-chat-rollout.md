# Citation lookup and evidence-backed chat

## Current state

The exact citation endpoint is available at `GET /api/v1/legal/provisions/by-citation` when `CITATION_LOOKUP_ENABLED=true`. `POST /api/v1/legal/search` uses the same evidence service and accepts a published `release_version`. Both return ordered per-reference outcomes and canonical evidence. Section 168 remains missing; Section 189 returns both stored identities. The historical/source edition notice must stay visible.

Conversation APIs, a dedicated Compose `chat-worker`, and the frontend chat flow are implemented. `CHAT_ENABLED=false` and `CHAT_GENERATION_ENABLED=false` are the safe defaults. Do not enable public generation until the gates below pass.

When the conversation API is disabled, the frontend explicitly says explanations are unavailable and leads with the best published source wording. For a topic search, a containing section is shown ahead of its top-ranked child clause when the section includes that clause verbatim; remaining matches follow. Retrieval rank is not presented as a confidence probability. In chat, validated explanation blocks appear before source cards. If generation fails validation, the explanation stays withheld and the strongest available source wording is shown with the failure notice.

Message history uses a bounded cursor, and the sidebar loads conversation pages on demand. Each live SSE subscription names its generation run so a later turn cannot replay an earlier answer into the current one. A user can select a stored ambiguous identity in the source inspector; the selected provision version is validated against the pinned release and carried into the run. Short follow-ups reuse a prior identity only when that identity is unambiguous. Semantic retrieval reloads ranked canonical versions with targeted database reads.

## Local configuration

1. Migrate with `cd backend && uv run alembic upgrade head`.
2. Start the database and API as usual. Start the dedicated worker with `docker compose up -d chat-worker` after rebuilding the backend image, or use `cd backend && uv run python -m app.chat.worker` locally.
3. The backend reads settings from the repository root `.env` when run from `backend/`. Set `CHAT_ENABLED=true` to expose conversation history, then set `DEEPSEEK_API_KEY` and `CHAT_GENERATION_ENABLED=true` only for a controlled validation environment. `DEEPSEEK_MODEL` defaults to `deepseek-v4-pro`; the HTTP adapter requests JSON output and validates the result locally. Keep the key outside Git.
4. `CHAT_GENERATION_KILL_SWITCH=true` stops new explanations. Exact lookup and source reading remain available.

For a private local preview using the retained isolated evaluation database, run `cd backend && uv run python scripts/local_chat_preview.py --database app_live_validation_20261009`. It starts the API, one worker, and Vite on loopback only; open `http://127.0.0.1:5173/`. The script requires an existing `app_live_validation_` database with a published corpus and the official DeepSeek endpoint. It sets one active generation and a US$2 Lagos-day application cap. Stop it with Ctrl+C. The normal `localhost:8000` service keeps its chat flags off.

The default shared active-generation limit is 100. `CHAT_MAX_ACTIVE_GENERATIONS` above 500 requires `CHAT_PROVIDER_CAPACITY_APPROVED=true` at startup. This flag records approval; it does not obtain provider quota. Each worker can process `CHAT_WORKER_CONCURRENCY=16` runs concurrently; scale workers and database/API capacity separately. The Lagos-day application cap is `CHAT_DAILY_BUDGET_USD=100`, with guest/account daily allowances of 20/200 and rolling one-minute allowances of 3/10. The spending ledger reserves conservative maximum cost before every generation and verification call; uncertain charges remain reserved after timeout.

The API uses `DATABASE_POOL_SIZE=40` to cover its synchronous request concurrency; the Compose chat and ingestion workers default to pools of 20. Keep the sum of possible connections across replicas below PostgreSQL's configured maximum, or use a connection pooler. A smaller API pool timed out under 100 concurrent conversation creations in the isolated load environment; 40 connections admitted all 100 in the repeat probe.

Completed runs retain stage times and retrieval fallback in `conversation_message.validation_result`. Worker logs record run ID, outcome, active count, token usage, reserved and actual micro-dollar amounts, and stage times; they exclude question and source text. Budget ledger rows remain the source of truth for spend reconciliation.

Deleting or expiring a conversation removes its messages, evidence snapshots, runs, and event traces. A provider reservation retains its ledger link with a null run ID, allowing an in-flight call to settle after the deletion. Uncertain charges stay reserved until reconciled.

## Validation gates

- Backend regression tests: `cd backend && uv run bash scripts/test.sh`. This command creates or uses a database ending `_test`, migrates it, and never runs destructive fixture cleanup against `app`. `TEST_DATABASE_URL` can select a different dedicated test database.
- Frontend type/build check: `bun run --filter frontend build`; lint: `bun run lint`.
- Evaluation set: `docs/constitution-explanation-evaluation-v1.json` contains 200 English cases across exact references, lists/ranges, topics, scenarios, follow-ups, and unanswerable requests. `cd backend && uv run python scripts/evaluate_explanations.py ../docs/constitution-explanation-evaluation-v1.json` checks deterministic identities. A nonzero exit with “human supported-answer review is pending” is expected until live captures and a full JSONL judgment file are provided with `--captures` and `--judgments`.
- Public generation gate: perfect deterministic citation and provenance checks, zero critical status errors, and at least 95% supported-answer judgments on the reviewed 200 cases. The cases currently have `review_status=pending_human_review`; this gate is **not met**.
- Capacity gate: the [isolated simulator trial](chat-load-test-2026-10-08.md) passed 1,000 active generations and SSE connections. The user confirmed DeepSeek quota for capped live validation, which has begun. Capacity for 1,000 concurrent provider calls has not been confirmed. The documented DeepSeek Pro concurrency limit is 500, so `CHAT_MAX_ACTIVE_GENERATIONS=1000` must remain disabled for public traffic until capacity is confirmed. Infrastructure throughput and provider quota must be reported separately.

The user is available to review the 200 cases, and the local `.env` supplies the DeepSeek key. Human judgments are still required before the quality gate can pass. The active `BAAI/bge-m3` Hugging Face query-embedding endpoint initially returned HTTP 402, so the first pilot used lexical fallback. After the user enabled quota, a query embedding returned the expected 1,024 dimensions and the full evaluation used the restored embedding path.

### One-case live probe on 2026-10-09

Case `e001` (`Section 1`) ran against a disposable database copy with one active generation and a US$0.05 application cap. The configured destination was `api.deepseek.com`. Generation and verification each made one settled request; together they spent 1,441 micro USD (US$0.001441), leaving zero reserved. The verifier stage did not pass the application's validation, so the explanation was withheld and official wording remained available. The original run did not record the specific verifier reason. Later runs now record a safe failure stage and reason without draft text.

The probe also exposed a provenance mismatch: `provision_version.text_sha256` is the normalized legal-text hash used by ingestion, while captured evidence was expected to hash the exact served wording. Evidence cards now contain the exact served-text hash and reject versions whose stored hash matches neither the served nor normalized text. A read-only audit found all 1,811 recovered versions consistent with the ingestion hash rule. The original failed capture is retained at `backend/storage/evaluations/failed-probe-2026-10-09.jsonl`; it is excluded from the 200-case evaluation. Public generation remains disabled.

### Capped live pilots on 2026-10-09

All live calls used an isolated `app_live_validation_20261009` database, a local API on port 18000, one active generation, an application cap of US$2 per Lagos day, and an exact-run inline worker. The worker only claims the API run ID returned for each evaluation turn. Earlier six-case prompt pilots are retained separately under `backend/storage/evaluations/pilot-*.jsonl`; none was mixed into a final 200-case capture.

A 24-case stratified pilot under prompt version `constitution-english-v4` captured all 27 turns without transport errors. Of those turns, 15 produced validated explanations, 8 returned insufficient evidence, and 4 withheld explanations after validation failed. The six sampled exact citations all completed. Several topic and scenario cases returned no evidence because the active Hugging Face query-embedding endpoint returned HTTP 402 and the lexical fallback found no match. The pilot captures passed all deterministic provenance checks.

After embedding access was restored, one six-case semantic probe recovered the expected path in four of five answerable cases. A complete, frozen `constitution-english-v4` evaluation then captured all 200 cases and 225 turns with no collector errors. All 90 deterministic identity checks and all capture provenance checks passed. Outcomes were 145 completed explanations, 57 validation failures, and 23 insufficient-evidence responses. Expected source paths were found in 49 of 50 topic cases and 19 of 25 scenarios. At least one turn was withheld in 48 of the 170 answerable cases, so even a perfect human judgment on every other case could support at most 152 of 200 cases. The 95% quality gate is **not met**. A later 24-case `constitution-english-v5` pilot completed 20 of 27 turns, versus 19 of 27 for those same case IDs in the v4 full run; this small change did not justify another full live run.

The isolated ledger recorded US$1.169394 total spent across all probes, pilots, diagnostics, and the full evaluation, with zero reserved at the last read. This is an application ledger amount, not a provider invoice. The full v4 capture and offline review page are in ignored `backend/storage/evaluations/full-v4-2026-10-09.jsonl` and `backend/storage/evaluations/review-v4-2026-10-09.html`. They are retained for human diagnosis, not for public release. Human supported-answer judgments remain pending. Public generation remains disabled.

A later loopback-only preview on the same isolated database completed a live Section 33(2)(a) explanation and displayed it above linked wording in the browser. The live “Presidential qualifications” question still failed deterministic grounding checks, so its generated draft remained hidden; the fallback now leads with the full Section 131 source wording. These spot checks do not change the failed public quality gate.

The subsequent prompt wording is tagged `constitution-english-v6`. It has not passed a new 200-case evaluation or human review.

The offline review page disables a “supported” judgment for an answerable case with any withheld turn. The evaluator enforces the same rule when checking exported judgments, so the quality gate cannot be passed by marking an unavailable explanation as supported.

The simulator and black-box load client are at `backend/scripts/chat_provider_simulator.py` and `backend/scripts/load_test_chat.py`. Run them only against a disposable deployment with the published test corpus on a separate API port. Bind the simulator to a private interface, set the worker's `DEEPSEEK_BASE_URL` to that interface and `DEEPSEEK_API_KEY=simulator-test`, and set `CHAT_ENABLED=true`, `CHAT_GENERATION_ENABLED=true`, `CHAT_MAX_ACTIVE_GENERATIONS=1000`, and `CHAT_PROVIDER_CAPACITY_APPROVED=true` in that isolated environment. Scale worker slots to at least 1,000 before measuring active provider calls; admission alone can otherwise leave runs pending. Start the simulator with `cd backend && CHAT_SIMULATOR_DELAY_SECONDS=30 uv run uvicorn scripts.chat_provider_simulator:app --host 127.0.0.1 --port 8089`. Run `cd backend && uv run python scripts/load_test_chat.py --base-url http://127.0.0.1:18000 --target 1000 --disposable-environment`. The JSON report separates accepted requests, terminal SSE events, and peak open SSE connections. Record worker/database metrics and provider call concurrency alongside that report. The simulator accepts every grounding claim by design and must never serve public answers.

### Live quality review

Use a separate disposable database and local API/worker stack for live DeepSeek validation. Set `CHAT_DAILY_BUDGET_USD` to a small explicit amount in both processes, `CHAT_MAX_ACTIVE_GENERATIONS=1`, and keep the normal public flags off. Verify the local API is pinned to the dataset's release. The collector refuses non-local API URLs and requires `--isolated-deployment`; it captures one case by default so the first call can confirm model access and ledger accounting without launching the full set:

```bash
cd backend
uv run python scripts/collect_explanation_review.py ../docs/constitution-explanation-evaluation-v1.json \
  --base-url http://127.0.0.1:18000 --output storage/evaluations/live-captures.jsonl \
  --max-cases 1 --isolated-deployment --inline-worker
```

The `--inline-worker` option requires a disposable database name beginning `app_live_validation_`, the official DeepSeek host, one active generation, an application cap no higher than US$2, and a matching run ID in that same database. It avoids a continuously running validation worker. Only after a small live check, embedding-provider availability, and spending review should collection resume with an explicit `--max-cases` value. Existing case IDs are skipped on rerun. A failed capture records its error and must be investigated before removing that row for a retry. Do not use the 1,000-call provider simulator to score legal quality.

Render the actual captured answers and canonical evidence for human review with `uv run python scripts/render_explanation_review.py ../docs/constitution-explanation-evaluation-v1.json --captures storage/evaluations/live-captures.jsonl --output storage/evaluations/review.html`. The offline page stores selections locally in the browser and exports `constitution-explanation-judgments.jsonl`. The reviewer marks every case supported or unsupported and explicitly marks whether a critical legal-status error occurred. A judgment is bound to its captured answer hash, so a changed answer needs review again. Then run `uv run python scripts/evaluate_explanations.py ../docs/constitution-explanation-evaluation-v1.json --captures storage/evaluations/live-captures.jsonl --judgments storage/evaluations/constitution-explanation-judgments.jsonl`. The evaluator rechecks captured evidence release, hashes, provenance fields, block references, quotations, and exact-case identities; all 200 captures and judgments are required. Keep the answer captures and judgments in ignored `backend/storage/evaluations/` until reviewed for retention.

Do not send draft answer tokens to clients. Workers publish stored source cards first, then persist the answer only after deterministic and separate model grounding checks pass. A failed explanation leaves the official source evidence visible with an explanation-unavailable state. Model review is a risk reduction step, not legal certification.

## Local corpus recovery on 2026-10-07

An earlier test fixture cleared the local `app` database. The original PDF stayed in the Docker ingestion volume. A release manifest (1,811 entries), retrieval document artifact (1,829 segments), and saved embedding checkpoint batches also survived. `backend/scripts/recover_public_corpus.py` verified all legal-text hashes and the published segment/vector aggregate checksums before rebuilding the public release in one database transaction. The live index then passed `validate_index_build`; Section 33 resolved, Section 168 stayed missing, Section 189 stayed ambiguous, and lexical search returned results. A new ignored dump is at `backend/storage/backups/app-recovered-2026-10-07.dump`.

The recovery did **not** restore deleted account data, candidate reviews, ingestion workflow records, audit history, or exact original whitespace at some multi-segment boundaries. The configured bootstrap superuser was recreated. These limits are recorded in the release validation report. Do not treat the reconstructed release as a complete recovery of the prior database. The source PDF SHA-256 and the 1,811 normalized legal-text hashes match the retained artifacts.

The recovery script is intentionally non-mergeable: it refuses a database with existing corpus rows and requires the original manifest, retrieval documents, embedding batches, and review evidence file. Its default mode validates without writing. Keep the ignored local dump or move it to a managed backup location; PostgreSQL WAL/PITR was not configured for the previous loss.

On 2026-10-09, a fresh ignored dump was saved at `backend/storage/backups/app-pre-chat-fixes-2026-10-09.dump` before the additive reservation and selected-identity migrations. The local `app` schema is at revision `9e0f1a2b3c4d`.
