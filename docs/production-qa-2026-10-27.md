# Production QA — 27 October 2026

Status: **26 findings tracked; 24 fixed and verified, QA-005 awaiting review and QA-025 open. Production sign-off withheld.**

Latest status and verification: see “Current fix-pass status — 28 October 2026” below. Original measurements and intermediate failures are preserved.

This is a living defect tracker. Keep IDs stable; update status, fix reference and verification evidence rather than deleting fixed defects. Severity: P1 blocks reliable release behavior; P2 materially affects a flow or accuracy; P3 polish/maintenance. Status: Open / In progress / Fixed and verified / Needs human review.

## Scope and environment

- Current working tree, including pre-existing uncommitted sidebar/chat/loading changes. Those changes are not attributed to this QA pass.
- Local Vite frontend (`localhost:5173`), Compose API (`localhost:8000`), PostgreSQL; actual active release `composite-2026-10-23-constitution-acja-police`.
- Actual published laws: Constitution 1999 (2004 source edition), ACJA 2015, Police Act 2020. Historical/as-enacted content is not certified current consolidated law.
- Backend regressions run exclusively through the guarded runner against the companion `_test` database; live corpus reads are separate.
- Browser regressions use mocked legal/chat responses where the existing specs do. These prove UI contracts, not live provider accuracy.
- Native-speaker translation review, deployed infrastructure, real low-end devices, sustained production load and current-law certification are outside what this local run proves.

## Defect tracker

| ID | Severity | Area | Defect | Status |
| --- | --- | --- | --- | --- |
| QA-001 | P2 | Mobile / translations | Translated composer metadata pushes Send onto a separate left-aligned row. | Fixed and verified |
| QA-002 | P2 | Search relevance | Translated governor eligibility queries rank disqualification (s.182) above qualification (s.177). | Fixed and verified |
| QA-003 | P2 | Search relevance | Nonsense and unrelated sports questions receive legal results without a relevance warning. | Fixed and verified |
| QA-004 | P2 | Language detection | Pidgin `police fit search my phone?` and `my right to bail` are reported as English. | Fixed and verified |
| QA-005 | P1 | Release assurance | All reader languages are enabled, but documented native/answer evaluation gates have no completed review evidence. | Needs human review |
| QA-006 | P3 | Product context | Project context says only the Constitution is public; current runtime publishes three laws. | Fixed and verified |
| QA-007 | P2 | Settings / scope | Settings presents only the Constitution edition and caveat for a three-law release. | Fixed and verified |

### QA-001 — Composer footer jumps on translated mobile screens

- Reproduce: viewport 375×812 → Find → choose Yorùbá → select all laws.
- Actual: purpose and edition labels take the row; Send wraps under them on the left. Short English copy keeps Send at the right. The helper line and character counter can also wrap inconsistently.
- Expected: stable right-hand Send control; translated context wraps in its own column; counter remains intact.
- Evidence: `output/playwright/production-qa/03-search-yoruba-mobile.png` (before).
- Fix: `ChatComposer.tsx` keeps the action in a non-wrapping footer, gives it a fixed non-shrinking 44px box, allows long metadata to wrap and protects the counter width.
- Verification: all 25 language/width combinations pass in `production-layout.spec.ts` (320, 375, 640, 768 and 1280px). After screenshot: `06-find-320-after.png`. Included in the final 112-test Chromium UI run.

### QA-002 — Translation paraphrases change the first result

- English `requirements to become governor` → Constitution s.177 first.
- Yorùbá `àwọn àmúyẹ láti di Gómìnà`, Hausa `sharuɗɗan zama Gwamna`, Igbo `ihe ntozu ịghọ Gọvanọ` → s.182 first, s.177 second.
- Provider renders these as variants of `What are the qualifications for becoming a Governor?`.
- Expected: positive eligibility question leads with s.177; disqualification remains a useful supporting result.
- Evidence: `output/playwright/production-qa/search-results.json` includes exact query, translated query, release, canonical identities, ranking and timing.
- Fix direction: cover equivalent English eligibility phrasings in topic matching, then run the existing held-out benchmark without tuning to held-out questions.

### QA-003 — Unrelated queries look relevant

- Reproduce: Find `zxqvplm nonsense xyz` or `Who won the World Cup?`.
- Actual: HTTP 200 with ranked provisions and `message: null`. Sports question led with Constitution s.162; nonsense led with ACJA s.276 in this run.
- Expected: a low-relevance/no-answer state or explicit confidence limitation, with optional broader matches separated from direct matches.
- Risk: a source-backed result can still be unrelated; retrieval presence is not proof of relevance.
- Fix direction: evaluate calibrated relevance/abstention on a negative-query set; avoid inventing a threshold from this small sample.

### QA-004 — Ambiguous Pidgin is silently called English

- Actual API `query_language` is `en` and `searched_query` is null for the two sample phrases above. Relevant sections still rank first in these cases.
- Root evidence: the cheap detector lacks a strong Pidgin marker in these borrowed-English phrases. `fit` is a cross-language collision; the model understanding call is skipped.
- Expected: supported Pidgin should retain its language for downstream answer-language selection, or ambiguous language should remain unspecified rather than confidently mislabeled.
- Fix direction: evaluate contextual Pidgin constructions (`fit` plus a verb), while retaining English uses such as `fit for office`. A native review must settle inherently ambiguous phrases such as `my right to bail`.

### QA-005 — Language launch assurance is incomplete

- Runtime capabilities advertise `en`, `pcm`, `yo`, `ha`, `ig`.
- `frontend/src/locales/README.md` explicitly labels all four non-English catalogues unreviewed drafts.
- `docs/multilingual-evaluation-plan.md` requires per-language retrieval parity, ≥98% deterministic answer-translation pass rate and zero dropped legal conditions in judged samples. It also says the ~60-answer-per-language evaluation set is not built.
- Current small retrieval samples and mocked translation tests do not satisfy those gates. Beta and English fallback are useful protections but do not establish semantic correctness.
- Required acceptance: native reviewer/date/coverage; versioned translation-answer evaluation; reproducible paired retrieval reports on benchmark and held-out sets.

### QA-006 — Repository product context trails runtime

- `PROJECT_CONTEXT.md` contains statements that ACJA and Police Act are unpublished and only one law appears in the picker. The current release and actual browser picker contradict those statements.
- Expected: distinguish dated historical notes from a clearly current rollout state. Verify review/promotion provenance before updating public claims.

### QA-007 — Settings understates available laws

- Reproduce: Settings → Profile → available edition on the actual composite release.
- Actual: Constitution-only display/caveat; Find correctly lists Constitution, ACJA and Police Act.
- Evidence: `output/playwright/production-qa/04-settings-yoruba-mobile.png` and `SettingsView.tsx`, which renders one `edition_label` through `editionName`.
- Expected: display the release's published instruments and each law's applicable source/edition caveat.
- Fix: Settings reads published instruments for the selected release, lists each source edition, and renders localized per-law caveats with consistent spacing. Failed instrument reads join the existing retry action.
- Verification: new multi-law Settings regression passes; actual Yorùbá settings was visually rechecked in light/dark mode.

## Initial baseline results

| Check | Result | What it establishes |
| --- | --- | --- |
| Frontend production build | Passed | TypeScript and production bundling succeed. |
| Backend suite | 721 passed, 4 skipped; 90% total measured coverage | Existing regressions pass on isolated test DB. Skips require external OCR/PDF prerequisites. |
| Selected browser suite | 53 passed | Desktop/mobile chat, Find, reading, source, save, translated UI and error/fallback contracts. |
| Live multilingual retrieval sample | 20/20 expected sections in top 5; 17/20 first | Four paired questions per language; small diagnostic sample, not the release gate. |
| Live request edge cases | Empty/whitespace/2,001 chars → 422; exact/range/scoped references return expected identities | Request validation and exact lookup paths behave correctly. |

Initial live sample mean request time: English 1.32s, Pidgin 1.45s, Yorùbá 1.70s, Hausa 2.09s, Igbo 1.81s (two concurrent requests, warm caches possible). Exact requests took 19–47ms. These are local diagnostic timings, not production p95 or a capacity test.

## Visual walkthrough

1. Desktop chat entry — readable hierarchy; existing sidebar/chat changes preserved (`01-chat-desktop.png`).
2. Exact Find result — source wording, edition disclosure and actions visible (`02-exact-search-desktop.png`).
3. Yorùbá mobile Find — defect QA-001 reproduced (`03-search-yoruba-mobile.png`).
4. Yorùbá mobile Settings — content readable, tabs horizontally scroll; scope defect QA-007 (`04-settings-yoruba-mobile.png`).

Screenshots and raw JSON are local QA artifacts under `output/playwright/production-qa/` (ignored by Git). Re-run to regenerate them; do not mistake absent artifacts on another checkout for tracked evidence.

## Additional defects and verification

| ID | Severity | Area | Defect | Status |
| --- | --- | --- | --- | --- |
| QA-008 | P2 | Responsive header | At 320px the header overflows to 328px; tablet text can squeeze out the mobile brand. | Fixed and verified |
| QA-009 | P2 | Admin / scrolling | Sticky header and toast obscure the Verify source action after scrolling. | Fixed and verified |
| QA-010 | P2 | Local development | Compose Watch rebuilds API/worker from generated test artifacts and interrupts requests. | Fixed and verified |
| QA-011 | P3 | Lint tooling | Biome checks generated browser session/result JSON and fails after a successful browser run. | Fixed and verified |
| QA-012 | P2 | Test isolation | Mocked admin token leaks to real chat-history requests, causing intermittent logout. | Fixed and verified |
| QA-013 | P2 | Multilingual retrieval | Hausa `sirri` and Igbo `nzuzo` are confidently treated as English and miss privacy s.37. | Fixed and verified |
| QA-014 | P2 | Live translation coverage | Yorùbá and Hausa examples complete only in English; first Hausa attempt fails at provider stage. | Fixed and verified |
| QA-015 | P3 | E2E repeatability | Repeated live auth suites exhaust production-style rate limits on the shared local IP/account. | Fixed and verified |
| QA-016 | P3 | Browser prerequisites | Cached Firefox/WebKit builds do not match the installed Playwright version. | Fixed and verified |
| QA-017 | P3 | Translated Browse | Edition warning is repeated in English beneath its localized version. | Fixed and verified |
| QA-018 | P3 | Cross-browser tests | Chromium-only clipboard permissions prevent Firefox/WebKit flow tests from starting. | Fixed and verified |

### QA-008 — Header overflows on narrow phones

- Measured `document.documentElement.scrollWidth=328` at `innerWidth=320` in all five interface languages. The settings action extends beyond the screen. At 640px, simultaneous mobile brand and desktop tagline squeeze the brand away.
- Fix: allow the mobile brand container to shrink, constrain artwork to its container, prevent action controls from shrinking, and defer the desktop tagline until the large breakpoint. Brand artwork and design tokens are preserved.
- Verification: 25 Chromium layout cases pass. Before/after: `05-find-320-before.png`, `06-find-320-after.png`.

### QA-009 — Scrolled admin action is covered

- Existing `admin.spec.ts` flow timed out on Verify source; its click log explicitly identifies the sticky language control, then a success toast intercepting the click. The action was otherwise visible and enabled.
- Fix: document scroll padding reserves space for the 64px sticky header and bottom notifications. No forced clicks or weakened actionability assertions were added.
- Verification: the complete confirm/review/verify/publish test passes; all 22 admin tests pass after also fixing QA-012.

### QA-010 — Test artifacts repeatedly recreate local services

- Evidence: an existing `docker compose watch` process; Docker lifecycle events show kill/destroy/create with restart count zero. This is recreation, not an application crash.
- Root cause: watch ignores under `path: ./frontend` redundantly began with `./frontend/`; generated test-results/auth/reports were also incompletely excluded. Frontend writes triggered rebuilds while live requests were active. The stopped worker left a QA run leased and capacity occupied until normal expiry.
- Fix: watch-relative exclusions for node_modules, dist, reports, results and auth. Exclude generated frontend build/coverage from backend sync. Config validates with `docker compose config --quiet`. The old watcher was stopped to apply the change.
- Recovery evidence: the interrupted QA lease expired automatically and `GenerationCapacity.active_count` returned from 1 to 0; no manual database repair or budget resets were used.
- Scope: local development configuration; not evidence of a deployed production crash.

### QA-011 — Generated browser state breaks lint

- Reproduce: authenticate/run Playwright, then non-mutating `bunx biome check .` from frontend. Generated `.auth/user.json` and `test-results/.last-run.json` fail formatting.
- Fix: exclude generated auth, test-results and blob-report folders in Biome; do not edit session contents to appease the formatter.
- Verification: non-mutating full frontend Biome check passes.

### QA-012 — Admin tests unexpectedly return to login

- Existing admin fixtures mock refresh and current user but not the shared sidebar conversation requests. With live chat enabled, the fake bearer token receives real 401 responses and the app correctly ends that invalid session. Failure snapshots show the login screen, not a missing compose control or broken SSE implementation.
- Fix: the admin helper mocks conversation capabilities/history as part of its existing fake session. Production auth behavior is unchanged.
- Verification: all 22 admin tests pass together with two workers, including compose, SSE reconnect and verification/publishing.

### QA-013 — Short native legal keywords bypass understanding

- Live Hausa `sirri` (benchmark privacy keyword) produces ACJA s.120/s.375/s.62; Igbo `nzuzo` produces ACJA s.263/s.494. Neither includes Constitution s.37 in the first five returned provisions.
- Both return `searched_query: null`: no translation. `detect()` treats words with no known function-word/signature match as confidently English.
- The Igbo live question `Kedu ihe Section 37 kwuru banyere nzuzo?` is also stored as `question_language: en`; explicit `answer_language: ig` still produces an Igbo translation. This demonstrates why a successful output-language override does not prove question detection.
- Expected: recognize supported legal vocabulary or defer uncertain input to understanding; preserve provider budget controls. Evaluate short-word ambiguity before broadening detection.
- Evidence: expanded search JSON and QA-only answer validation metadata. Do not tune against the held-out set.

### QA-014 — Live enabled languages are not consistently delivered

- One paired Section 37 question per language, with explicit output language. English completes in 10.35s; Pidgin completes with checked translation in 16.61s; Yorùbá completes with English fallback in 16.56s; Igbo completes with checked translation in 17.73s.
- Yorùbá rejection metadata: `The translation is still in English`. The original English answer remains, as designed. The existing UI regression verifies the English fallback note.
- Hausa first attempt returns `provider_failure` in 9.92s. One bounded retry completes in 23.44s but has no attached Hausa translation, so remains an English fallback.
- This is a delivery/coverage finding, not proof that rejected translations were shown or that a legal claim was wrong. Native semantic accuracy and preservation of every condition still need the documented review gates.
- Evidence: `answer-results-first.json`, `answer-results-ha-retry.json`, `answer-validation.json`. No production data or user messages are needed for the sample.

### QA-015 — Repeated auth suites hit real limits

- Initial full browser run: 114/116 passed; failures were the now-addressed admin issues. A later 142-test run reached four additional live login/signup failures. Bounded API logs confirm 429 responses.
- Limits are 10 login attempts per IP/account per 15 minutes and 10 signup attempts per IP per hour. Repeating the suite naturally exhausts these. Guest answer limit of three submissions per minute was also observed; remaining probes waited for allowance rather than disabling limits.
- Expected test setup: isolated test app/database and deliberate rate-limit tests, with an explicit repeatable local QA workflow. Do not treat these failures as successful auth tests or weaken shared app protections to obtain a green run.
- Final 112-test mocked UI run passes. Full fresh-window live auth sign-off remains distinct.

### QA-016 — Cross-engine executables are mismatched

- Firefox and WebKit were present in cache but their revisions did not match this checkout. Launch fails before page creation (for example missing `webkit-2336/pw_run.sh`). These are environment failures, not 66 application regressions.
- Added `frontend/playwright.qa.config.ts` to run the 33 mocked language/layout/law-reading cases per engine without real login or provider calls. Matching official browser builds are installed for verification.

## Expanded live relevance sample

Ten paired topics per language, selected from the existing draft benchmark (50 legal queries), plus 12 request/reference/negative-query edge cases. All 62 requests completed with an HTTP response on the stable run. Results are scored by instrument plus canonical section identity, not display text. This is a small diagnostic sample; it is not the full benchmark/held-out language gate.

| Language | Expected section first | Expected section in top 5 | Mean local request time |
| --- | --- | --- | --- |
| English | 10/10 | 10/10 | 0.969s |
| Pidgin | 10/10 | 10/10 | 1.373s |
| Yorùbá | 9/10 | 10/10 | 1.688s |
| Hausa | 9/10 | 9/10 | 1.563s |
| Igbo | 8/10 | 9/10 | 1.804s |
| Total | 46/50 | 48/50 | — |

Hausa governor ranking varied between the initial and expanded run; preserve both captures rather than claiming deterministic parity. None of the sampled legal-query misses returned an HTTP error: availability alone would have hidden the problem.

Reproduce: `python3 backend/scripts/production_qa_probe.py`. It makes at most two concurrent requests and preserves raw responses, timings, translated queries and canonical identities in `search-results-expanded.json`. Provider calls use the running app budget. Failed infrastructure requests have null retrieval scores rather than being counted as accuracy misses.

## Feature improvements to consider

- Relevance-aware abstention for Find, including unrelated-domain and nonsense queries.
- A concise per-law source/edition summary in Settings, consistent with Find and answer cards.
- A visible native-review status for interface translations as well as answer translations.
- A repeatable per-language dashboard of retrieval hit@1/hit@5, translation fallback rate, condition-preservation judgments and latency. Keep provider/prompt/release versions with every report.
- Cross-browser CI projects (Firefox/WebKit are currently commented out), narrow screens and translated long-copy layout checks.

## Update protocol

For every fix, append commit/PR, test names, fresh evidence and date to the defect. Mark fixed only after the reproduction fails to reproduce and relevant regressions pass. Keep unresolved provider/native-review issues open rather than replacing them with optimistic estimates.

## Original-audit verification ledger (superseded by fix-pass results)

- Backend: **721 passed, 4 skipped, 90% total coverage**; mypy, ty, Ruff lint and format pass.
- Frontend: production TypeScript/Vite build and full non-mutating Biome check pass. No dependency lockfiles changed.
- Chromium: **112/112** final UI checks pass, including **25/25** language/viewport combinations and **22/22** admin checks. A new Settings regression covers all three source editions/caveats.
- Earlier full suite outcomes are retained above; the passing mocked set does not erase the four later rate-limited live-auth cases.
- Safety checks: no corpus text, release promotion, retrieval embedding, published-law status or production deployment changed. Synthetic QA guest conversations are labelled `Production QA 2026-10-27`.
- Screenshots 06–08 show the corrected narrow layout and multi-law Settings, including Yorùbá dark mode.

Final measurements and remaining limits are recorded below.

### QA-017 — Browse repeats a translated warning in English

Severity P3. **Fixed and verified.** On Yorùbá Browse, the localized edition notice was immediately followed by the same warning in English next to the section count. The second copy came directly from `selected.edition_note`. Removed that duplicate; the full localized per-law notice remains above the count. Official source headings and legal wording continue in English. A new locale regression verifies the Yorùbá warning and count and rejects the redundant English sentence; it passes in Chromium, Firefox and WebKit. Evidence: `09-browse-yoruba-dark-after.png`.

### QA-018 — Clipboard permissions make otherwise portable tests fail before navigation

Severity P3. **Fixed and verified.** The existing law-reading tests requested Chromium-only `clipboard-read` / `clipboard-write` permissions unconditionally. Firefox and WebKit rejected those permission names before testing the page. The fixture now preserves native clipboard permission/read-back testing on Chromium, and uses a browser-local Clipboard API stub to verify the exact payload on Firefox/WebKit. Remaining law switching, source panels, save, reload and export checks execute normally. Native clipboard interoperability on those two engines still requires a manual device/browser check.

### Final cross-browser and performance results

| Check | Result | Limit |
| --- | --- | --- |
| Firefox layouts | 25/25 passed | Desktop engine at responsive viewport sizes, not a physical Android device. |
| WebKit layouts | 25/25 passed | WebKit automation, not a physical iPhone/Safari installation. |
| Firefox + WebKit locale/law flows | 18/18 passed after fixture correction | Native clipboard is stubbed on these engines; Chromium covers the native path. |
| Latest affected Chromium copy/source/settings flows | 42/42 passed | Follows the earlier 112/112 complete mocked UI run; includes the added Browse-copy regression. |
| Quiet exact-search load smoke | 100/100 HTTP 200 with nonempty results, 5 clients; p50 49.82ms, p95 168.48ms, max 310.98ms; 1.48s elapsed | Local development API; exact references only. Not an LLM throughput test or production SLO. |
| Contended exact-search smoke | 100/100 succeeded; p95 3,690.91ms, max 6,063.34ms | Ran alongside browser suites/provider checks on the same machine. Retained separately; illustrates local resource contention, not an isolated app benchmark. |
| Watcher generated-file probe | API and worker container IDs/start times unchanged after result-file write/removal | Existing watcher restarted with corrected ignores and bounded local AI-preview overlay. |
| Frontend build/static checks | TypeScript/Vite and non-mutating Biome passed after final product edits | No lockfile/dependency edits. Matching browser executables were downloaded to the Playwright cache. |

Raw performance captures: `exact-search-load.json` (contended), `exact-search-load-quiet.json` (quiet). Cross-browser evidence lives in `cross-browser-verified/` (initial portability failures + all 50 passing layouts) and `cross-browser-flow-final/` (18 passing flow tests). Keeping those runs separate avoids rewriting earlier failures as passes.

Reproduce focused cross-engine checks from frontend: `bunx playwright test --config=playwright.qa.config.ts --workers=2`. This now includes the extra translated-Browse test (34 cases per engine, 68 total). Installed engines: Firefox 153.0 / Playwright build 1538; WebKit 26.5 / build 2336. Do not infer a production-browser support policy from these local checks.

### Final visual walkthrough and artifacts

1. Desktop chat entry: healthy hierarchy and initial state; screenshot `01-chat-desktop.png`.
2. Exact Find: canonical source wording and disclosure visible; `02-exact-search-desktop.png`.
3. Translated phone Find: composer/header defects reproduced, then corrected; `03-search-yoruba-mobile.png`, `05-find-320-before.png`, `06-find-320-after.png`.
4. Settings: three source editions and localized per-law caveats now visible; `07-settings-all-laws-after.png`; dark palette reviewed in `08-settings-yoruba-dark.png`.
5. Browse: localized edition notice retained once; dark translated layout reviewed; `09-browse-yoruba-dark-after.png`.

At the end of the original audit, ten of the first 18 findings were fixed and eight were open or required review. The fix-pass status below supersedes those counts. Earlier failures and measurements are retained as historical evidence.

## Fix pass — 27 October 2026

Work continues against the same tracker; earlier measurements remain historical evidence.

- QA-002 **In progress**: separate the governor's positive qualification hint (s.177) from disqualification (s.182); retain s.182 as required explanation context. Added paraphrase and disqualification regressions.
- QA-003 **In progress**: nearest-neighbour results whose leader lacks keyword/topic corroboration now carry the existing localized `not_covered` warning. No uncalibrated embedding threshold or silent rejection of legitimate semantic searches is introduced.
- QA-004 / QA-013 **In progress**: distinctive native content words and contextual Pidgin `fit + verb` trigger understanding; English `fit for office`, borrowed-English ambiguous phrases and curly-apostrophe contractions remain English. Privacy keywords also retain provider-independent topic hints. Regression checks are running on the dedicated test database.

### Fix-pass progress: translation and isolated browser QA

- Targeted backend regressions: **111 passed** on the companion `_test` database. This covers native keywords, contextual Pidgin/English collisions, governor qualification/disqualification, dense-only warnings, translation repair, and timeout fallback.
- QA-014 **In progress**: translation prompt v2 distinguishes locked English citations from translated prose. A rejected translation gets at most one corrected attempt, using the same spend reservations and checks. Provider failures with uncertain charges are not retried. Translation has a 60-second phase budget bounded by the remaining run deadline, preserving verified English on timeout.
- Additional finding QA-019 **In progress**: the old semantic translation judge omitted missing-fact prompts and follow-up questions. The v2 judge now checks every displayed item for target language, meaning and preserved conditions. Deterministic checks apply to all items and reject introduced numeric values as well as dropped ones. Tests prove repair, all-field coverage and safe fallback; native-speaker release approval remains separate.
- QA-005 remains **Needs human review**. Non-English interface options now visibly carry Beta, as translated answers already do. No glossary or catalogue is falsely marked reviewed.
- QA-015 **In progress**: a new runner creates a uniquely named disposable `_e2e_test` database, seeds its own QA account, starts loopback-only API/frontend servers, keeps rate limits on, and removes only its own database/processes afterward. Browser state is written to a run-specific artifact path. Shared app rate counters and corpus are untouched. Full verification is running.

- QA-006 **Fixed and verified (documentation)**: a read-only database check confirms active release `composite-2026-10-23-constitution-acja-police`, approval recorded 24 October, all three public instruments and verified source statuses (Constitution official; Acts trusted secondary). `PROJECT_CONTEXT.md` now starts with that dated local snapshot and explicitly marks the previous rollout notes historical. This does not assert current-law certification, native review, or remote deployment parity.

- QA-015 verification update: the first isolated full run reached **143/144** with no 429 failures. The remaining assertion hard-coded `localhost` despite the correct redirect to the configured `127.0.0.1` origin; it now uses the trusted Playwright `baseURL`. A second fresh run of all live auth/reset/signup flows passed **30/30** with rate limits enabled. Each run removed its own database and services. A final full isolated run is underway.
- Additional finding QA-020: the unsafe-redirect browser assertion assumed a hostname rather than the configured app origin. **Fixed and verified** by the 30-case real auth run; the security assertion still requires the exact trusted root URL.

### QA-021 — Explicitly selecting the published edition breaks semantic search

Severity **P1**. **Fixed and verified.** The first release-pinned 525-query run completed
40 exact lookups but all 485 semantic requests returned `503: This published
edition has no ready retrieval index`. The search route accepts only `ready`
builds; publication deliberately changes the active build to `promoted`. Unpinned
search and exact references hide this bug. It affects Browse-originated topic
searches and any search URL carrying a published release.

Fix: accept ready or promoted builds only within the already validated published
release scope; failed/building/unpublished indexes remain excluded. Regressions
cover both production and retired published releases plus rejection of failed
indexes. The failed full evaluation is retained as
`fix-reader-retrieval-before-pinned-fix.json`; it does not establish language
accuracy. A corrected full run will follow.

- Full isolated browser verification is now **144/144 passed**. Rate limits remained enabled; the disposable database and both server process groups were removed afterward. `bun run test` now uses the isolated workflow by default; `bun run test:live` explicitly targets the shared local stack. Frontend/backend READMEs document prerequisites, artifacts, rate limits and cleanup.
- Additional finding QA-022 **Fixed (documentation)**: the old frontend test instructions recommended `docker compose down -v` as routine cleanup, which removes shared database volumes. Replaced that guidance with the runner's scoped automatic cleanup and corrected the backend's stale container-test instructions. No shared volumes were deleted.
- The native review work is now concrete in `docs/reader-language-review-checklist.md`; all reviewer fields remain pending. The 525-query runner provides separate per-language benchmark/held-out parity gates, not a fabricated native approval.

### QA-023 — A stale standalone worker competes with the current Compose worker

Severity P2. **Fixed and verified (local operations).** The first live
fix-pass captures completed in all languages, but prompt metadata showed Igbo was
still `answer-translation-v1` with the old English language guess. The other
non-English captures used v2. A read-only process/mount check found a day-old
standalone `uv run python -m app.chat.worker` process alongside the current
Compose worker; Python workers do not reload imported code automatically.

After confirming zero pending/running generations, the identified old host
worker was terminated. The current Compose worker remains. The original mixed
captures are retained in `fix-answer-validation.json`; Igbo is being repeated in
`fix-igbo-current-worker.json`. They are not represented as five v2 successes.
Use one managed local worker workflow and restart all workers after code updates,
with a drain check before stopping an old process.

## Current fix-pass status — 28 October 2026

This section supersedes the intermediate “in progress” notes above. Production
sign-off remains withheld for QA-005 and QA-025. A successful HTTP response is
not a correct answer, and automated language checks are not native approval.

| ID | Severity | Finding | Current status |
| --- | --- | --- | --- |
| QA-019 | P2 | Translation judge omitted missing-fact and follow-up items | Fixed and verified |
| QA-020 | P3 | Auth redirect regression assumed localhost | Fixed and verified |
| QA-021 | P1 | Published/promoted retrieval index rejected when release pinned | Fixed and verified |
| QA-022 | P3 | Test cleanup docs recommended deleting shared volumes | Fixed and verified (documentation) |
| QA-023 | P2 | Old standalone worker processed jobs with old prompts | Fixed and verified (local operations) |
| QA-024 | P2 | “Explain Section 37 to me” treated as an unfinished range | Fixed and verified |
| QA-025 | P1 | Question understanding changes meaning; multilingual retrieval parity fails | Open; release blocker |
| QA-026 | P3 | Saved empty-state block action nested inside a paragraph | Fixed and verified |

### Verified changes to the original findings

- QA-002: the full benchmark now leads with s.177 for the Pidgin, Yorùbá, Hausa
  and Igbo governor-qualification questions; disqualification has its own hint.
  s.182 remains supporting context rather than replacing positive qualifications.
- QA-003: uncorroborated semantic leaders carry the localized `not_covered`
  warning. The UI uses neutral “Search matches” rather than “Best match”. Sports
  and nonsense API regressions pass; the live sports view was visually checked
  (`10-search-relevance-after.png`). This is a corroboration warning, not a
  calibrated universal relevance classifier.
- QA-004: contextual `fit + verb` constructions now trigger understanding while
  English fitness wording and contractions remain English. `my right to bail`
  remains English because the words alone do not distinguish English from
  Pidgin; explicit output-language selection remains available. This closure
  covers the reproducible contextual-detection defect, not perfect code-switching.
- QA-013: native content markers trigger understanding; both `sirri` and `nzuzo`
  now include Constitution s.37 in the first five on the full benchmark. This
  does not imply every short native keyword is recognized (see QA-025).
- QA-014 / QA-019: live Pidgin, Yorùbá and Hausa requests completed with checked
  translation v2. Igbo was repeated after removing the stale worker and completed
  with `question_language: ig` and translation v2 in 32.38s. The original mixed
  v1/v2 evidence is preserved. All displayed fields now get deterministic
  validation; judged languages also get all-field language/meaning/condition
  checks. At most one repair follows a rejected translation, with a bounded
  deadline and verified-English fallback. Five live examples are not a delivery
  SLO or a native accuracy sign-off.
- QA-015 / QA-020: the complete isolated browser suite passed **144/144**, including
  real authentication flows with rate limits enabled. A separate root-command
  smoke passed **2/2**. Each run removed only its own database and servers.
- QA-021: all **525/525** release-pinned requests completed after accepting a
  published release's promoted index. Fourteen API regressions cover this route,
  including production/retired published releases and rejected failed indexes.
- QA-023: the repeated Igbo capture proves the current worker and v2 prompt.
  Worker lifecycle guidance is in `backend/README.md`.

### Full multilingual retrieval evidence

Capture: `output/playwright/production-qa/fix-reader-retrieval.json`, release
`composite-2026-10-23-constitution-acja-police`, understanding v1. These are
measurements before the final QA-024 parser fix; do not rewrite them as a later
passing run. Every request completed, but the accuracy gate did not pass.

| Language | Benchmark hit@5 | Held-out hit@5 | Parity gate (both splits) |
| --- | --- | --- | --- |
| English | 100% (57/57) | 100% (40/40) | Reference |
| Pidgin | 97.01% (65/67) | 97.5% (39/40) | Pass |
| Yorùbá | 95.52% (64/67) | 90% (36/40) | Fail |
| Hausa | 91.04% (61/67) | 85% (34/40) | Fail |
| Igbo | 92.54% (62/67) | 95% (38/40) | Fail |

The gate requires hit@5 within five percentage points of English separately on
both splits. No held-out misses were used to tune individual topic rules.

### QA-024 — Ordinary “to me” prose is parsed as a range

The benchmark exposed correct question translations such as “Explain Section
37 to me” returning `reference_format` with no results. The citation parser
recognized `to` as a range delimiter and demanded another number. It now treats
`to me` / `to us` as ordinary trailing prose. Explicit numeric ranges and malformed
hierarchy rejection remain covered. Targeted citation/search suite: **81 passed**.
Live original and translated examples are retained in
`fix-explanation-references.json`. This general parser fix was derived from the
benchmark, not individual held-out failures.

### QA-025 — Question translations can change the reader's intent

The complete benchmark contains provider renderings that alter the requested
meaning before retrieval. Examples: Hausa senator-recall wording becomes a loan
application; an Igbo presidential-office question becomes landlord eligibility;
a Yorùbá mistreatment question becomes arrest authority. Some native short phrases
are still reported as English. Numeric checks alone cannot detect changed verbs
or offices. Correct sources for the rendered English can therefore be irrelevant
to the original reader message.

**Open / P1**: do not approve native-language production accuracy from these
results. Acceptance requires a versioned question-understanding evaluation with
independent native adjudication, controls for changed intent and uncertain
renderings, then a fresh full retrieval report and the existing answer review
gates. The existing answer-translation judge operates after English drafting and
does not establish faithfulness of the input-question translation. Provider/model
or prompt changes require new evidence; do not hard-code benchmark translations
or relax the gate to get a pass. Review tasks and required evidence are in
`docs/reader-language-review-checklist.md`.

### QA-026 — Empty saved state uses invalid block nesting

Browser console reports `<p> cannot contain a nested <div>` when Saved has no
bookmarks: the shared `EmptyState` wraps arbitrary React children in a paragraph,
while Saved includes a block containing its Find action. The body wrapper is now
a `div` with the same design-token classes. This preserves the intended spacing
and supports both plain text and action content. Pre-existing primitive styling
changes were preserved.

### Final fix-pass verification ledger

- Backend: **752 passed, 4 skipped; 90% measured coverage** after the final parser
  fix. Mypy, ty, Ruff lint and format pass. The narrower 81-case citation/search
  run precedes this complete run; its 34% coverage is not the full-suite baseline.
- Frontend: final TypeScript/Vite production build and full non-mutating Biome
  check pass. No lockfiles or dependency versions changed.
- Browser: **144/144** complete isolated Chromium suite passed earlier in this
  fix pass. After the final search heading/empty-state edits, the affected
  legal-home run passed **21 existing flows**, including desktop/mobile
  copy/source/save/reload. The new warning case separately passed **1/1** in
  1.4s after using DOM readiness plus explicit UI assertions.
- Intermediate affected runs are retained: one assertion initially matched two
  status regions (corrected to the warning's text); other retries timed out on
  navigation/load. Those runs are not represented as complete passes. No force
  clicks, arbitrary sleeps, disabled rate limits or relaxed production checks
  were used. The final isolated services/databases were cleaned by their runner.
- QA-024 live: English, Yorùbá and Hausa explanation requests return exact Section
  37. The Igbo live rendering did not reproduce the same English suffix and
  remains within the broader QA-025 uncertainty; it is not counted as an exact
  translation success for this fix. Numeric-range/malformed-reference regressions
  remain green in the complete backend suite.
- QA-026: the empty-state wrapper now permits block children, and the affected
  browser flows pass. Browser diagnostics originally exposed the invalid nesting;
  the final frontend log no longer contains that nesting warning.
- Fresh screenshots: `10-search-relevance-after.png` (warning + neutral heading)
  and `11-language-beta-after.png` (all four native options visibly Beta).
- Local development watcher restored using the corrected ignores and existing
  Compose AI overlay. The stale standalone worker remains stopped. No release
  promotion, corpus/source text, shared rate counters or deployed environment
  was changed.

Remaining work is explicit: **QA-025 requires question-understanding correctness
work and a new passing evaluation; QA-005 requires the native/catalogue/glossary
and versioned answer reviews.** Neither is closed by Beta badges or test passes.
