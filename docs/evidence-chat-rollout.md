# Citation lookup and evidence-backed chat

Controls, validation gates and their status for exact citation lookup and
generated explanations. The answer pipeline itself is described in
[`architecture.md`](architecture.md#answers); the reasoning behind it is in
[ADR 0002](adr/0002-evidence-boundary-and-server-citations.md).

## Behaviour

- `GET /api/v1/legal/provisions/by-citation` and `POST /api/v1/legal/search`
  share the evidence service and accept a published `release_version`. Both
  return ordered per-reference outcomes and canonical evidence. In the
  Constitution source edition, Section 168 is missing and Section 189 returns
  both printed identities. The source-edition notice stays visible.
- With the conversation API disabled, the frontend says explanations are
  unavailable and leads with the best published source wording. Retrieval rank
  is never shown as a confidence.
- In chat, source cards are sent first; a validated explanation is shown above
  them. If generation fails validation, the explanation is withheld and the
  strongest source wording is shown with a notice.
- Each SSE subscription names its generation run, so a later turn cannot replay
  an earlier answer. A reader can pick one of several stored identities in the
  source inspector; the chosen version is validated against the pinned release.

## Configuration

`backend/app/core/config.py` defaults are safe: `CHAT_ENABLED=false` and
`CHAT_GENERATION_ENABLED=false`. Explanations are produced only when both are
true and `CHAT_GENERATION_KILL_SWITCH` is false (`Settings.explanations_enabled`).
Production values are in `render.yaml`.

| Setting | Effect |
| --- | --- |
| `CHAT_GENERATION_KILL_SWITCH=true` | Stops new explanations; also checked before every paid call. Lookup and reading continue. |
| `CHAT_DAILY_BUDGET_USD`, `CHAT_MONTHLY_BUDGET_USD`, `AI_MONTHLY_BUDGET_USD` | Lagos-day and month caps enforced by the spend ledger (`backend/app/chat/budget.py`). |
| `CHAT_GUEST_DAILY_LIMIT`, `CHAT_ACCOUNT_DAILY_LIMIT`, `CHAT_GUEST_BURST_LIMIT`, `CHAT_ACCOUNT_BURST_LIMIT` | Per-reader daily and one-minute admission limits (`backend/app/api/routes/conversations.py`). |
| `CHAT_MAX_ACTIVE_GENERATIONS` | Global cap on pending and running generations; above 500 it also needs `CHAT_PROVIDER_CAPACITY_APPROVED=true`. |
| `CHAT_WORKER_CONCURRENCY` | Runs processed at once per worker. |
| `CHAT_EVIDENCE_MAX_CHARS` | Size limit for the evidence packet sent to the model. |
| `CHAT_LANGUAGES_ENABLED` | Reader languages offered. |
| `DEEPSEEK_MODEL`, `DEEPSEEK_API_KEY` | Provider model and key. Keep the key out of Git. |

To run chat locally, start the stack as in [`development.md`](development.md),
set `CHAT_ENABLED=true`, `CHAT_GENERATION_ENABLED=true` and `DEEPSEEK_API_KEY` in
the ignored root `.env`, and start a worker with
`cd backend && uv run python -m app.chat.worker` (or the Compose `chat-worker`
service). `compose.ai.yml` sets a one-generation, low-budget local preview.

Completed runs keep stage timings and the retrieval mode in
`conversation_message.validation_result`. Worker logs record the run ID,
outcome, token usage, reserved and actual cost and stage timings, never the
question or source text. Budget ledger rows are the source of truth for spend.
Deleting or expiring a conversation removes its messages, evidence, runs and
events; a provider reservation keeps its ledger row with a null run so an
in-flight call can still settle.

## Validation gates

- **Regression tests.** `cd backend && uv run bash scripts/test.sh` creates or
  uses a database whose name ends in `_test`; the fixtures refuse any other
  database. Frontend: `bun run lint` and `bun run build`.
- **Public generation gate.** On the evaluation set
  `eval/datasets/constitution-explanation-evaluation-v1.json`: perfect
  deterministic citation and provenance checks, zero critical legal-status
  errors, and at least 95% supported-answer judgments from human review of 200
  cases. Every case is still `pending_human_review`; **this gate is not met.**
- **Capacity.** `CHAT_MAX_ACTIVE_GENERATIONS` above 500 is refused at startup
  without `CHAT_PROVIDER_CAPACITY_APPROVED=true`, which records approval and
  does not obtain provider quota. Provider capacity and infrastructure
  throughput must be measured and reported separately. The provider simulator
  and load client for disposable environments are
  `backend/scripts/chat_provider_simulator.py` and
  `backend/scripts/load_test_chat.py`; the simulator accepts every grounding
  claim and must never serve readers.

### Evidence recorded so far

- **9 October 2026, prompt `constitution-english-v4`.** A frozen run captured
  all 200 cases (225 turns) on an isolated database with a US$2 daily cap:
  145 completed explanations, 57 validation failures and 23
  insufficient-evidence responses; all deterministic identity and provenance
  checks passed. At least one turn was withheld in 48 of the 170 answerable
  cases, so at most 152 of 200 could be judged supported. No human judgments
  were recorded. The application ledger recorded US$1.169394 for all probes,
  pilots and the full run.
- A one-case probe on the same day exposed a mismatch between the normalised
  text hash used by ingestion and the hash of the served wording. Evidence cards
  now carry the served-text hash and reject a version whose stored hash matches
  neither.
- **29 October 2026, prompt `constitution-english-v11` on `deepseek-flash`.**
  A 100-question comparison graded by models, not people:
  87 of 100 questions returned an explanation after fixes, 74 were judged a
  direct answer, and mean accuracy was 1.76 out of 2. It is not the 200-case
  human gate.
- Prompt v11 also passes scripted-provider tests in `backend/tests/chat/`,
  which exercise retrieval, validation, budgeting and persistence with a fake
  model. They show the pipeline's contracts, not live answer quality.

## Launch exception (recorded 16 November 2026)

`render.yaml` enables public answer generation (`CHAT_ENABLED=true`,
`CHAT_GENERATION_ENABLED=true`, `CHAT_GENERATION_KILL_SWITCH=false`) with
`DEEPSEEK_MODEL=deepseek-flash` and all five reader languages. On 16 November
2026 the owner decided to record this as an exception to the public generation
gate above rather than switch generation off.

**Gate not met.** The 95% supported-answer gate on 200 human-reviewed cases.
Every case in `constitution-explanation-evaluation-v1.json` is
`pending_human_review`, and `backend/scripts/evaluate_explanations.py` exits with
status 2 until captures and a complete judgment file are supplied. The last full
capture used prompt v4, could have supported at most 152 of 200 cases, and was
not judged. The deployed prompt (`constitution-english-v11`,
`backend/app/chat/__init__.py`) and model (`deepseek-flash`) have had no 200-case
capture and no human grounding review.

**Evidence for the deployed prompt and model.** Only the model-graded
100-question comparison of 29 October 2026 and the scripted-provider tests
listed above.

**Safeguards in force.**

- Citations, edition labels and source links are built from stored metadata,
  not model text (`backend/app/legal/evidence.py`).
- When text is served, its hash is recomputed and checked against the stored
  hash (`evidence_item` in `backend/app/legal/evidence.py`).
- Deterministic validation of every answer block: supplied evidence IDs only,
  quotes present in the cited text, cited sections and named laws inside the
  block's evidence, no description of how the answer was produced, and no
  claim that historical text is current law (`validate_draft` in
  `backend/app/chat/validation.py`).
- A separate model verifier reviews every block; a missing or malformed verdict
  rejects the answer (`validate_verifier` in `backend/app/chat/validation.py`).
- Fail-closed handling: a rejected opening block, a provider or schema error, or
  an exhausted budget withholds the explanation and shows the source wording;
  draft text is never streamed, and the answer is published only after both
  checks (`process_run` and `_finish` in `backend/app/chat/worker.py`).
- Edition notices on every answer: the Constitution's source-edition note and
  "As enacted, may have been amended" for Acts (`_edition_notice` in
  `backend/app/chat/worker.py`).
- Translated answers are checked deterministically and, for Yorùbá, Hausa and
  Igbo, by a back-translation judge; any failure returns the English answer.
  Non-English answers are labelled Beta (`backend/app/chat/translation.py`).
- Spend: worst-case cost is reserved before every paid call and settled
  afterwards; uncertain charges stay reserved (`backend/app/chat/budget.py`).
  `render.yaml` sets a US$5 Lagos-day cap and US$155 monthly caps.
- Admission limits in `render.yaml`: 3 explanations per guest and 10 per account
  per day, 1 and 2 per minute, and one answer generated at a time across the
  service, with up to five questions admitted and waiting in order.
- `CHAT_GENERATION_KILL_SWITCH` stops new explanations without a code change.

**Risk accepted.** Readers can receive explanations whose grounding has passed
the automated checks but has not been reviewed by a person. The verifier is a
model, so an answer can pass both checks and still be unsupported or misleading.
The published text is the source edition, so an accurate explanation of it can
differ from current law. Non-English answers rely on unreviewed glossaries.

**What closes the exception.** Capture the 200-case set live on the deployed
prompt and model, record human supported-answer and critical-status judgments
for every case with the offline review page, and run `evaluate_explanations.py`
with the captures and judgments until it exits with status 0. If the prompt or
model changes, the review applies to the new pair, not the old one.

## Live quality review procedure

Use a disposable database whose name starts with `app_live_validation_` and a
local API and worker. Set a small `CHAT_DAILY_BUDGET_USD`,
`CHAT_MAX_ACTIVE_GENERATIONS=1`, and pin the API to the dataset's release. The
collector refuses non-local URLs and requires `--isolated-deployment`; it
captures one case unless told otherwise:

```bash
cd backend
uv run python scripts/collect_explanation_review.py ../eval/datasets/constitution-explanation-evaluation-v1.json \
  --base-url http://127.0.0.1:18000 --output storage/evaluations/live-captures.jsonl \
  --max-cases 1 --isolated-deployment --inline-worker
```

`--inline-worker` also requires the official DeepSeek host, one active
generation, a cap no higher than US$2 and a run ID from that database. Resume
with an explicit `--max-cases` only after checking the first capture, embedding
availability and spend. Existing case IDs are skipped on rerun; a failed capture
records its error and must be investigated before it is retried.

Render the captures for review:

```bash
uv run python scripts/render_explanation_review.py ../eval/datasets/constitution-explanation-evaluation-v1.json \
  --captures storage/evaluations/live-captures.jsonl --output storage/evaluations/review.html
```

The page stores selections in the browser and exports a judgments file. The
reviewer marks every case supported or unsupported and records whether a
critical legal-status error occurred. A judgment is bound to the hash of the
captured answer, and "supported" is disabled for an answerable case with a
withheld turn. Then:

```bash
uv run python scripts/evaluate_explanations.py ../eval/datasets/constitution-explanation-evaluation-v1.json \
  --captures storage/evaluations/live-captures.jsonl \
  --judgments storage/evaluations/constitution-explanation-judgments.jsonl
```

The evaluator rechecks the captured release, hashes, provenance, block
references, quotations and exact-case identities, and needs all captures and
judgments. Captures and judgments stay in the ignored `backend/storage/`
directory until reviewed for retention.

## Corpus recovery, October 2026

A test fixture once cleared a local development database. The public release was
rebuilt from the retained source PDF, release manifest, retrieval documents and
embedding checkpoints by `backend/scripts/recover_public_corpus.py`, which
verifies every legal-text hash and the segment and vector checksums before
writing in one transaction, and refuses a database that already has corpus rows.
Account and review history could not be recovered. Since then, the test runner
refuses any database whose name does not end in `_test`.
