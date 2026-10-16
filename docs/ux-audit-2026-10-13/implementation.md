# UX remediation implementation

13 October 2026 · constitution.ng · Source revision `source-eeb2c8053a7bf1bd`

The twenty states captured in the [original audit](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/report.md) are mapped below to the implemented changes. The intermittent New conversation failure is covered by component isolation, cancellation of abandoned browser requests, and guards against late responses. Refresh is no longer the recovery mechanism.

## Coverage of all twenty captured states

| Step | Audited state | Implemented behavior and evidence |
| --- | --- | --- |
| 1 | Live entry | Stable Ask a question and Find a section tabs; explicit capability metadata and retryable availability notice. History failures no longer change the task. |
| 2 | Topic search | Find always performs provision lookup. Submitted searches use a compact header and bring the loaded result into view. The rebuilt API includes the workspace's existing topic/title improvements; this is not a new model-quality certification. |
| 3 | Guest Settings profile | Guest identity and sign-in actions replace the example account. Signed-in profile editing uses the account API. Save, cancel, reload and failed-storage behavior have regressions. |
| 4 | Settings preferences | Durable Enter-to-send, follow-latest and open-sources preferences affect their actual flows. Accessible tabs support arrow navigation. English is the supported language; unsupported language and notification promises were removed. |
| 5 | Chat entry | Suggested questions focus the editor. Enter, Shift+Enter, Ctrl/Cmd+Enter and IME behavior are explicit. A 2,000-character limit and counter match the API. Drafts survive reload within the browser tab. |
| 6 | Completed answer | Copy answer with citations, Save sources, Export answer, Export chat and Helpful/Not helpful actions are connected. Copies and exports retain source edition and provenance. |
| 7 | New after completion | New clears the answer, question, run, errors and selected source; the composer is empty, enabled and focused. Desktop and mobile regressions pass. |
| 8 | New during a run | New detaches from the previous request/run and immediately provides an editable new chat. The old durable conversation can be reopened independently. |
| 9 | Submission failure | The editable question is preserved. Retry reuses the created conversation and idempotency key. Edit question and Find relevant sections provide recovery actions. |
| 10 | Desktop source inspector | A sticky, independently scrollable inspector offers Copy source and Save source, with shared edition wording and release-pinned links. |
| 11 | New with source open | Selected evidence belongs to the conversation component boundary and cannot leak into a fresh chat. |
| 12 | Late acceptance | A response from an abandoned request cannot redirect the user or replace the new chat. The delayed-acceptance regression verifies this race. |
| 13 | Mobile answer reading | Source cards show concise titles on narrow screens. Comfortable source controls, conditional automatic scrolling and Jump to latest improve reading. Completion brings the explanation into view; reading older content retains the reader's position. |
| 14 | Mobile source sheet | The existing modal source reader now includes working copy/save actions and the same historical notice as chat, Find and full provision views. |
| 15 | Mobile navigation/history | History has search, Today/Yesterday/Earlier groups, dates and an explicit active chat. Guests can sign in or create an account. Importing guest chats remains an explicit account action. |
| 16 | Mobile New | New closes the drawer and restores focus to the empty editor after the closing transition. The drawer also has a visible close control. |
| 17 | Browse Constitution | The local API was refreshed to include the current descriptive chapter/topic code. Browse search explicitly opens Find and creates zero conversations in its regression. Coverage wording says “available” chapters and sections. |
| 18 | Exact section lookup | The introduction collapses after submission. Focus and scrolling wait for the real result instead of the loading placeholder. Desktop and mobile delayed-result regressions pass. |
| 19 | Original source context | Shared source actions, currency notices and release-pinned document links keep provenance visible. Historical wording is also present when an explanation is withheld or unavailable. |
| 20 | Saved empty state | Browse and Find links provide a direct starting action. Bookmarks can be exported. Settings can export research or clear local bookmarks/drafts after confirmation, without clearing account authentication. |

## Conversation and product quality

Follow-ups now use bounded, release-pinned context: prior user questions and actually cited provision identities. General follow-ups can continue a multi-source answer. Ambiguous pronouns or subsections produce a clarification instead of a guessed referent. A selected identity for the duplicate printed Section 189 is retained through subsequent turns. The worker uses prompt version `constitution-english-v8`; earlier assistant prose is not treated as legal evidence.

Interrupted SSE streams expose Reconnect and Check answer status. Persisted conversation polling recovers a finished answer even if its terminal event is lost. Browser request cancellation, immediate submission guards and retry identity protect navigation and avoid duplicate submissions.

Answer usefulness feedback is stored separately from legal-grounding validation, with one owner-controlled rating per assistant message. A superuser-only quality panel exposes aggregate outcomes, finished answers, mean completion duration and feedback counts for the previous 24 hours. It does not return raw questions or certify that an answer is legally correct.

The frontend and API expose matching source build IDs in Settings → Security → Support details. The generated client was regenerated from the backend. Client generation now formats only its output, and Docker dependency installation uses the frozen Bun lockfile. The revision script hashes packaged sources and configuration without including local secrets or build output.

## Verification

- **38 browser regressions passed** across chat, Find/Browse and Settings. These use mocked APIs and include desktop/mobile New, delayed acceptance, active runs, failed retry, lost SSE completion, drafts, IME, accessible tabs, durable preferences, account actions, export and delayed search positioning.
- **70 backend tests passed** against the isolated `app_test` database: chat workers, validation, conversation ownership, capabilities, feedback, aggregate metrics, legal search and topic matching.
- The frontend production build, scoped Biome checks, backend Ruff, mypy and ty checks passed. The full Docker image build passed with frozen dependencies; the local API is healthy on the final source revision.
- **90 deterministic corpus evaluation cases passed with zero failures.** Live model captures and the 200-case human supported-answer review remain pending; the evaluator deliberately does not mark that rollout gate passed.
- The additive feedback migration, `a0f1b2c3d4e5`, was applied locally after a database backup. Existing corpus text and identities were not rewritten.
- Desktop/mobile screenshots were visually reviewed. Chat screenshots below use synthetic answers; live screenshots use the rebuilt local API. No model-generation call was made for this work.

Tests: [chat browser regressions](/Users/amosgodwin/WebstormProjects/law-padi/frontend/tests/chat-home.spec.ts), [Find regressions](/Users/amosgodwin/WebstormProjects/law-padi/frontend/tests/legal-home.spec.ts), [Settings regressions](/Users/amosgodwin/WebstormProjects/law-padi/frontend/tests/user-settings.spec.ts), [backend UX contracts](/Users/amosgodwin/WebstormProjects/law-padi/backend/tests/chat/test_ux_contract.py).

## Before/after evidence

The refreshed chat shows the explanation, historical notice and useful research actions together. This answer is a synthetic fixture, not evidence of live model quality.

![Updated answer, synthetic replay](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/after-answer-replay.png)

Mobile New opens an empty, focused editor with the navigation drawer closed.

![Mobile New, synthetic replay](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/after-mobile-new-replay.png)

The mobile source reader keeps the exact wording, edition notice and copy/save actions together.

![Mobile source reader, synthetic replay](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/after-mobile-source-replay.png)

The rebuilt live Settings screen displays supported preferences and actual guest/account state. Support details confirm that app and service builds match.

![Live Settings preferences](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/after-live-preferences.png)

Additional live evidence: [guest profile](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/after-live-settings.png), [build diagnostics](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/after-live-build-details.png), [exact source result](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/after-live-section.png), [descriptive chapter browse](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/after-live-browse.png), [Saved starting actions](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/after-live-saved.png).

## Remaining product milestones

The local service keeps its existing disabled chat/generation configuration. Search, Browse and source reading remain available. Chat interaction regressions use synthetic fixtures, while backend tests enable capabilities in an isolated test environment.

The published source remains the historical 2004 compilation. Current-law consolidation, reviewed alterations, the missing Section 168 text, and human resolution of corpus identities require authoritative source work. The application continues to disclose the missing/ambiguous cases rather than invent text. Translations, account-synced bookmarks, an actual mobile keyboard and comprehensive screen-reader/contrast/zoom verification remain separate milestones. None is presented as delivered by these UI changes.
