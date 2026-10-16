# constitution.ng UX and product quality audit
13 October 2026 · Current workspace frontend, local running API, and controlled chat replay

The strongest next investment is reliable conversation continuity and truthful product behavior. The existing calm visual style, source-linked answer layout and readable mobile source sheet are worth keeping. A person should be able to ask, understand, verify, continue and keep an answer without guessing what the app did.

This audit contains ten recommended work packages. “Confirmed” means observed in this run or directly established by current code. “Code risk” means a concrete implementation gap whose failure frequency was not measured. “Opportunity” is a proposed improvement, not a defect.

**Scope and limits**

The normal local API returned 503 for conversations because chat is disabled. The frontend was reviewed against that live API for entry, search, browse, exact lookup, source context, Settings and Saved. A separate temporary API on port 8001 and frontend on 5181 replayed synthetic conversation, submission and SSE responses against the unchanged current frontend. This reproduced chat state bugs without enabling generation, calling an LLM, modifying the corpus, or creating conversations in the real database. Replay screenshots have “replay” in their filenames and must not be used as evidence of real answer quality.

The running API is older than the workspace: its search.py SHA-256 was ce9979f4ecf4d54d9a3b5a94573be891eb4138b46e91f3916006adc24480efb7; the workspace value was d968026702227dbd543fe4fd819410f157c896e425b068cd6287d06aefa30d36. app/legal/topics.py exists in the workspace and was missing in the running container. Findings about missing titles and the live search ranking concern this older runtime. The newer retrieval implementation was inspected but not evaluated against a rebuilt live backend.

Screenshots were saved and visually inspected. Desktop capture used the default 1280 × 720 viewport; mobile replay used 390 × 844. The temporary viewport override was reset. No application source was changed. The existing uncommitted work was preserved. This is not a completed accessibility certification, a security audit, a production performance benchmark, or a new legal-answer evaluation.

**The reported New conversation bug: reproduced**

Expected: New opens a clean, writable chat immediately and remains there unless the user chooses a conversation.

Observed:
- After a completed answer, New removes the conversation ID from the URL but the previous answer remains.
- During an answer, New leaves the composer disabled and retains the old pending question. Stop answering is ineffective. Refresh makes the composer usable again.
- New with an open source inspector retains the old selected source.
- New before a delayed message acceptance briefly shows the empty chat, then the late response redirects back to the abandoned conversation.
- On mobile, New changes the URL but leaves the navigation drawer open.

The main cause is [ChatHome.tsx](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/ChatHome.tsx:515): the cleanup runs only when search.c is truthy. Returning to a fresh chat makes it undefined, so runId, liveAnswer and pendingQuestion survive. The cleanup also omits selectedEvidence, draft and title-editing state. activeRunId falls back to the old runId at line 513, disabling the composer at line 948. The SSE effect stops subscribing when there is no conversation ID at line 642, while Stop exits immediately under the same condition at line 695. This combination explains the stuck state and why a reload clears it.

The second cause is [the submit callback](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/ChatHome.tsx:604): after awaiting acceptance it sets state and navigates without checking whether the user has since started another chat. A route change alone is not a reset when the same component remains mounted. React documents that state persists at the same position in the tree; a changed key can reset it, but this app also needs an explicit reset for New when already on the empty-chat URL. [React state reset guidance](https://react.dev/learn/preserving-and-resetting-state).

**1. Make New conversation one reliable action — P1, confirmed**

Implement one start-new action shared by the sidebar and top bar. It should reset the draft, pending question, live answer, run, progress, errors, source selection, title edit and message pagination; clear conversation/query/release/selected URL context; close the mobile drawer; and focus the composer. It must also work when the route is already the empty-chat route.

Associate transient state and every async callback with a conversation ID and an interaction revision. Abort abandoned browser requests where possible, and ignore any late callback whose revision no longer matches the user's current intent. Detach from the previous run rather than letting it disable the new chat; a durable old run can remain available when its conversation is reopened.

A key-based component boundary can help isolate conversations, but changing the key only by conversation ID would still miss New clicked twice on the empty route. Do not remove only the truthy check and assume the acceptance-navigation race is solved.

Evidence: steps 7, 8, 11, 12 and 16; [cleanup](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/ChatHome.tsx:515), [late navigation](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/ChatHome.tsx:604), [mobile New link](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/Sidebar/AppSidebar.tsx:74).

Acceptance: completed answer → New; running answer → New; delayed POST → New; open source → New; New twice; switch A to B with late A responses. Each yields the intended chat, a usable composer, correct sources and no forced refresh.

**2. Let people recover from failed or interrupted answers — P1, confirmed submission weakness plus SSE code risk**

The draft clears before either conversation creation or message acceptance succeeds. A controlled 503 showed a question bubble and an error, but an empty editor with no Retry/Edit action. If the first submit fails after creating the conversation, the URL never receives that created ID; another attempt can create another empty conversation and a new idempotency key.

Preserve the editable question until acceptance, or restore it on failure. Retain the newly created conversation ID and submission key across retries. Add explicit Retry, Edit question and Read relevant sections actions. Distinguish offline, temporarily unavailable, rate-limited and stopped states, with an actual next action and allowance/reset details when the API supplies them.

The stream handler at [ChatHome.tsx](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/ChatHome.tsx:641) displays “Reconnecting” but has no terminal recovery handler, catch around stream consumption, or run-status polling after retry exhaustion. This was inspected, not reproduced to its final retry limit. After a stream ends unexpectedly, re-read persisted run/conversation state and show a bounded recovery path.

Evidence: step 9 and [submission](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/ChatHome.tsx:560).

Acceptance: a transient 503 preserves an editable question; retry submits once to the same conversation; an exhausted reconnect shows a recoverable state; server completion remains discoverable after a lost terminal event.

**3. Make Settings real and remove misleading promises — P1, confirmed code and UI**

A guest sees a hard-coded Amos Godwin profile and example email. Save changes only runs setSaved(true). Language selection and preference toggles do not persist or affect the answer path. Export, Clear local activity and Change password have no handlers. “Email verified,” Corpus 0.3.0 and Languages 5 are static claims. The current worker requests plain English, despite the UI promising five answer languages.

Connect identity and profile editing to actual account data, persist supported preferences, and verify their effects. Show a guest state when signed out. Use actual release and capability metadata. Hide or clearly disable unfinished actions; success should mean a durable write succeeded. Offer English as the supported answer language until translations are actually implemented and evaluated. Replace preview privacy text with an accurate account of processing and retention; the code contains an external model adapter when generation is enabled.

Evidence: steps 3–4; [Settings state](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/SettingsView.tsx:92), [hard-coded profile](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/SettingsView.tsx:134), [save flag](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/SettingsView.tsx:305).

Acceptance: saved preferences survive reload and change the corresponding behavior; guest identity is accurate; every visible action works or visibly explains its availability; no unsupported language or verification claims remain.

**4. Make Ask and Find section predictable, with the result in view — P1, confirmed design coupling**

The product decides whether to show chat by whether conversation history loaded successfully. A network/history failure therefore changes the app into search mode and alters navigation labels. That query disables retry on mount, reconnect and focus, making a transient failure sticky. History health is also not a reliable indication that generation is enabled: the API gates those separately.

Browse Search navigates to the same q URL used to auto-submit a chat question. With chat enabled, an action called Search can create a conversation and request an explanation. With chat disabled it returns provision matches. The first viewport after a live search still shows the full welcome area rather than the result.

Keep a stable entry experience with two clearly named intents: “Ask a question” and “Find a section.” Determine capabilities explicitly, and handle history loading errors within history. Keep deterministic search available independently of generation. Give disabled explanations a clear, retryable status. Replace the large welcome area with a compact search header once results exist and move focus to the result/status.

Evidence: steps 1–2, 17–18; [mode switch](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/LawPadiHome.tsx:32), [history retry policy](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/hooks/useConversations.ts:26), [Browse submission](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/BrowseConstitution.tsx:24).

Acceptance: a failed history request does not silently change task meaning; Find does not trigger generation; the submitted query and useful result are visible promptly at desktop and mobile sizes.

**5. Make legal currency and coverage equally clear in every answer state — P1, confirmed code gap**

The captured source is explicitly a historical 2004 edition, and successful chat rendering includes an amendment caveat. That is a strength. The no-block fallback branch returns before that same historical notice: a withheld/provider-failure answer can display official wording without the successful answer's explanation of later amendments. “2004 edition” alone does not tell a casual reader whether the rule still applies.

Use one consistent edition/coverage component for explanations, fallback wording, full sections, shared/exported answers and saved research. Say plainly “2004 source edition; later amendments are not included.” Provide source authority, publication edition and last verification details when actually known. A current consolidated corpus with reviewed alterations is a major product milestone; visual labels cannot substitute for that work.

The repository also documents missing Section 168 and ambiguous Section 189 identities. Those cases were not independently re-tested in this audit. They should remain explicit corpus-quality tasks and receive dedicated lookup/coverage tests before any “every section” claim is made.

Evidence: steps 6, 10, 14, 18–19; [fallback branch](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/ChatHome.tsx:282), [successful notice](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/ChatHome.tsx:364), [rollout context](/Users/amosgodwin/WebstormProjects/law-padi/docs/evidence-chat-rollout.md:1).

Acceptance: every historical-text state carries the same usable notice; source gaps and ambiguous identities are disclosed; nobody has to infer “current” from an authoritative-looking card.

**6. Make follow-ups work like a continuing conversation — P2, code limitation and opportunity**

Suggested follow-ups already exist and the answer layout supports “What could change this for you.” The worker only reuses prior source identity when it can resolve one evidence identity. Multi-source answers can therefore lose the referent in short questions such as “What are the exceptions?” The model receives the previous user question, not a structured account of the preceding answer and accumulated user facts.

Maintain a small, release-pinned context record: discussed provisions, the question being continued, and relevant user-provided facts. Treat references as ambiguous when necessary and ask “Do you mean the privacy right or its limitations?” rather than guessing. Suggested questions should name their subject clearly and retain the relevant source context.

For personal scenarios, turn suitable missing facts into optional clarification prompts. Lead with a short explanation, preserve the conditions that matter, and offer deeper wording progressively. Guidance about practical next steps should use separately verified sources when it extends beyond the Constitution; do not invent remedies from this corpus.

Evidence: steps 6 and 13; [relative query restrictions](/Users/amosgodwin/WebstormProjects/law-padi/backend/app/chat/worker.py:186), [previous question](/Users/amosgodwin/WebstormProjects/law-padi/backend/app/chat/worker.py:224). No live multi-turn model quality test was run.

Acceptance: evaluate follow-ups after multi-source answers, corrections of facts and “what about my case?”; ask a clear clarification when context is ambiguous, preserving citation and release identity.

**7. Make asking quick and natural — P2, confirmed implementation gaps**

The textarea sends only with Ctrl/Cmd+Enter and shows no shortcut hint. Example chips fill it without focusing it. There is no client length limit/count matching the API's 2,000-character limit, no persisted per-chat draft, and no explicit scroll management for new messages. These are everyday sources of small friction.

Choose an explicit input convention. Enter to send and Shift+Enter for a newline is familiar for chat, with IME composition handling; if Ctrl/Cmd+Enter stays, expose that hint. Focus the editor after an example or New, preserve drafts by conversation, warn before the actual length limit and keep a visible send affordance. Keep the composer reachable during a long conversation; auto-follow only when the reader is already near the latest message and offer “Jump to latest” otherwise.

Evidence: steps 1, 5 and 13; [composer keyboard behavior](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/ChatComposer.tsx:56), [API length limit](/Users/amosgodwin/WebstormProjects/law-padi/backend/app/chat/schemas.py:51), [example buttons](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/ChatHome.tsx:952).

Acceptance: keyboard-only question flow is obvious; composing in an IME does not submit accidentally; a long pasted question is handled before an avoidable server error; new messages do not drag a reader away from older content.

**8. Finish mobile navigation and accessible interactions — P1 for mobile New, P2 for the wider pass**

The mobile source sheet is readable and the core layout reflows well. Mobile New does not close the drawer, whereas history/main links do. Users must dismiss the overlay before continuing, adding to the impression that New failed. The drawer currently lacks an obvious visible close button in the captured state.

Close the drawer for every completed navigation action and restore appropriate focus. Give it an accessible, visible dismissal control. Review source chips, switches and close actions for useful touch areas, focus indicators and screen-reader names. Settings uses manually declared tabs without the corresponding keyboard behavior or panel associations; use the existing accessible tab primitive or implement the full pattern.

The W3C tabs pattern specifies arrow-key movement and associated tab panels. WCAG's target-size requirement includes spacing exceptions, so small visible chips are a testing risk, not by themselves proof of a violation. Aim for comfortable 44-pixel interactive areas where feasible. [W3C tabs guidance](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/), [target size guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).

Evidence: steps 4 and 13–16; [New link](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/Sidebar/AppSidebar.tsx:74), [tabs](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/SettingsView.tsx:110).

Acceptance: test keyboard-only navigation, source opening/closing, visible focus, settings arrows, mobile drawer dismissal, 200% zoom and an actual mobile keyboard. Full contrast, screen-reader and device verification remain outstanding.

**9. Make useful answers easy to keep and return to — P2, opportunity grounded in existing flows**

Full provision views support copy/share/save, and Saved honestly says bookmarks stay on the device. Those actions are missing from the chat answer/source inspector. The empty Saved screen offers instructions but no direct starting action. History has pagination, but no search, date grouping or selected-conversation indicator. Guests have no visible sign-in entry in the captured main navigation.

Add Copy answer with citations/edition, Save source directly in chat and an export/share flow that preserves provenance. Add a Browse action to the empty state, simple history search/date grouping and a visible active chat. Give guests an unobtrusive sign-in path with a clear explanation of what is local and what persists. Keep guest-chat claiming explicit and user-controlled, matching the existing backend design. Account-synced bookmarks can be a later milestone, clearly disclosed until shipped.

Evidence: steps 6, 10, 15 and 20; [answer rendering](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/LawPadi/ChatHome.tsx:333), [local bookmarks](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/hooks/useSavedProvisions.ts:4), [guest navigation](/Users/amosgodwin/WebstormProjects/law-padi/frontend/src/components/Sidebar/User.tsx:47).

Acceptance: keep a cited source without leaving chat; copy an answer without losing its edition; find a previous useful chat; a guest understands storage and optional account benefits.

**10. Make each release prove that the core experience works — P1, confirmed runtime/test drift**

The observed API is behind the frontend/workspace. Its everyday phone question returned a legislative-investigation section, and Browse lacked the new descriptive titles. The workspace already contains topic retrieval and titles intended to improve this. A source change is not a delivered improvement until the running app uses it.

Build and verify frontend, API and worker from one identified revision. Expose safe build/corpus identifiers for diagnostics. Re-run the plain-language retrieval benchmark and human-supported answer review against the exact release that will serve users, including fallback states and multi-turn questions. The repository's rollout guide says the earlier full quality gate was not met; the newer prompt's current quality is not established by this audit.

Add meaningful browser regression coverage for work packages 1–4 and 8. Existing settings tests still expect the retired “My profile,” “Password” and “Danger zone” tabs, while current UI has Profile/Preferences/Security. That mismatch was inspected; the full suite was not executed.

Measure time to first useful answer, accepted questions that reach completion, retry/reconnect outcomes, successful New actions, fallback frequency by cause, source engagement and optional user usefulness feedback. Use minimal operational metadata and explicit feedback; do not add recording of sensitive question text by default.

Evidence: steps 2 and 17; container/workspace hash comparison; [current test selectors](/Users/amosgodwin/WebstormProjects/law-padi/frontend/tests/user-settings.spec.ts:7), [rollout guide](/Users/amosgodwin/WebstormProjects/law-padi/docs/evidence-chat-rollout.md:1).

Acceptance: core regressions pass against the actual release; build IDs agree; new retrieval/answer evaluations are attached to the release; usefulness and failure recovery can be measured separately from server availability.

**Recommended implementation order**

First implement 1, 2 and the mobile New part of 8. Then replace the fake Settings behaviors in 3 and stabilize task meaning/result placement in 4. Follow with input improvements in 7, consistent legal notices in 5 and research/context improvements in 6 and 9. Apply 10 throughout delivery. Preserve the current visual system and improve density progressively; a visual redesign is not needed to remove these failures.

**Captured steps and general health**

| Step | Description | Health | Environment |
|---|---|---|---|
| 1 | Live search entry | Usable with limitations | Live local API |
| 2 | Live topic search, first viewport | Needs improvement | Live local API |
| 3 | Guest Settings profile | Broken product behavior | Live local API |
| 4 | Settings preferences | Broken product behavior | Live local API |
| 5 | Chat entry with controlled API | Good starting point | Controlled replay |
| 6 | Completed replay answer | Good structure | Controlled replay |
| 7 | New after a completed answer | Confirmed bug | Controlled replay |
| 8 | New during an active answer | Confirmed blocking bug | Controlled replay |
| 9 | 503 on first message submission | Confirmed recovery weakness | Controlled replay |
| 10 | Desktop source inspection | Useful with friction | Controlled replay |
| 11 | New while a source is open | Confirmed bug | Controlled replay |
| 12 | New before delayed acceptance | Confirmed navigation race | Controlled replay |
| 13 | Mobile reading at 390 × 844 | Readable with friction | Controlled replay |
| 14 | Mobile source sheet | Healthy basic interaction | Controlled replay |
| 15 | Mobile drawer, stable capture | Usable drawer | Controlled replay |
| 16 | Mobile New conversation | Confirmed bug | Controlled replay |
| 17 | Live Constitution browse | Usable with build limitations | Live local API |
| 18 | Live exact Section 37 lookup | Works, result too low | Live local API |
| 19 | Live source context | Works with reading friction | Live local API |
| 20 | Live Saved empty state | Clear but passive | Live local API |

**Screenshots and notes**

**Step 1: Live search entry — Usable with limitations**

The calm emerald palette, clear question field and everyday examples help first-time use. Explanations are visibly unavailable. Guest identity and a sign-in path are absent from the main navigation. Keyboard focus and contrast need broader checks.

![Step 1: Live search entry](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/01-entry.jpg)

**Step 2: Live topic search, first viewport — Needs improvement**

After submitting a question, the large welcome area still fills the first viewport; the actual result starts below it. The older API returned Section 129 as best match for the phone-search example. That result was inspected in the DOM, but is below this screenshot. This is evidence about the running older build, not the newer retrieval code.

![Step 2: Live topic search, first viewport](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/02-search.jpg)

**Step 3: Guest Settings profile — Broken product behavior**

A guest sees Amos Godwin, amos@example.com, Corpus 0.3.0 and Languages 5. These are hard-coded display values. Save changes only sets a local success flag. No actual profile persistence was performed in this audit.

![Step 3: Guest Settings profile](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/03-settings-profile.jpg)

**Step 4: Settings preferences — Broken product behavior**

Language coverage is presented as available for five languages, while the current worker prompts for plain English. The language select is uncontrolled and toggles stay in component state. Pressing ArrowRight on Preferences did not move focus or selection; tabs lack aria-controls and roving tab indices.

![Step 4: Settings preferences](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/04-settings-preferences.jpg)

**Step 5: Chat entry with controlled API — Good starting point**

Natural questions and a dominant chat composer are a sound foundation. Suggestions fill the composer but leave focus on the button. Model quality cannot be inferred from this replay.

![Step 5: Chat entry with controlled API](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/05-chat-entry-replay.jpg)

**Step 6: Completed replay answer — Good structure**

The explanation precedes linked citations, source cards and a suggested follow-up. This is a synthetic test answer and establishes rendering behavior only. Copy, save, share and feedback controls for the answer itself are absent.

![Step 6: Completed replay answer](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/06-answer-replay.jpg)

**Step 7: New after a completed answer — Confirmed bug**

The URL no longer has a conversation ID and the welcome heading returns, but the previous answer and its source card remain visible. The new link navigated correctly; component state was not reset.

![Step 7: New after a completed answer](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/07-new-chat-stale-answer-replay.jpg)

**Step 8: New during an active answer — Confirmed blocking bug**

The empty-chat URL retains the old pending question and run. The question input is disabled. Clicking Stop answering has no effect because its handler requires a conversation ID. Reloading restored an enabled input. This intentional in-progress state is the bug evidence, not an unfinished capture.

![Step 8: New during an active answer](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/08-new-chat-disabled-replay.jpg)

**Step 9: 503 on first message submission — Confirmed recovery weakness**

The error message is visible, but the editable draft is empty and no Retry or Edit question action appears. The question survives only as a displayed bubble. The request had already created an empty conversation.

![Step 9: 503 on first message submission](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/09-submit-failure-replay.jpg)

**Step 10: Desktop source inspection — Useful with friction**

The exact wording, edition notice, document information and actions are grouped coherently. The pane consumes substantial chat width and has no copy/save action inside it. Its fixture PDF and full-section URLs were inspected, not opened.

![Step 10: Desktop source inspection](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/10-source-panel-replay.jpg)

**Step 11: New while a source is open — Confirmed bug**

The fresh-chat welcome screen retains the prior conversation's selected source pane. Selected evidence has no reset on conversation changes.

![Step 11: New while a source is open](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/11-new-chat-stale-source-replay.jpg)

**Step 12: New before delayed acceptance — Confirmed navigation race**

Immediately after New, the URL was the empty-chat URL. When the delayed POST completed, the app navigated into the abandoned conversation and displayed its answer. The acceptance response was delayed eight seconds by the fixture.

![Step 12: New before delayed acceptance](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/12-late-navigation-replay.jpg)

**Step 13: Mobile reading at 390 × 844 — Readable with friction**

Answer text and cards reflow without visible horizontal overflow in this state. Full source cards consume considerable vertical space and the composer is below the first viewport. A real mobile keyboard was not tested.

![Step 13: Mobile reading at 390 × 844](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/13-mobile-chat-replay.jpg)

**Step 14: Mobile source sheet — Healthy basic interaction**

The bottom sheet presents readable wording, source context and actions. Keyboard trapping and screen-reader behavior were not comprehensively tested. The PDF itself was not opened.

![Step 14: Mobile source sheet](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/14-mobile-source-replay.jpg)

**Step 15: Mobile drawer, stable capture — Usable drawer**

History and navigation are available in a compact drawer. This accepted image replaced a screenshot captured during the opening animation. Conversation titles truncate, and the current history item has no explicit selected state in its rendering code.

![Step 15: Mobile drawer, stable capture](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/15-mobile-navigation-replay.jpg)

**Step 16: Mobile New conversation — Confirmed bug**

The route changes to the empty-chat URL while the modal drawer remains open over the content. Existing history links and main navigation close the drawer; the New link lacks that handler.

![Step 16: Mobile New conversation](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/16-mobile-new-drawer-open-replay.jpg)

**Step 17: Live Constitution browse — Usable with build limitations**

The tree is structured and searchable. The older API provides chapter numbers without the newer descriptive titles, making the long list less informative. No claim is made that current workspace title code is missing.

![Step 17: Live Constitution browse](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/17-browse.jpg)

**Step 18: Live exact Section 37 lookup — Works, result too low**

Exact lookup returns the canonical text and release-pinned source actions. The full-page capture shows the result begins after the large introductory area. This was a read-only lookup; bookmark persistence and clipboard delivery were not exercised.

![Step 18: Live exact Section 37 lookup](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/18-exact-section.jpg)

**Step 19: Live source context — Works with reading friction**

The source inspector displays historical edition context, text, document and authority. Page 38 and the release-pinned PDF link were verified in the DOM; they are below the visible portion of this screenshot. A second PDF tab was not opened.

![Step 19: Live source context](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/19-original-source.jpg)

**Step 20: Live Saved empty state — Clear but passive**

Device-local storage is honestly disclosed and the empty state explains Save. There is no direct Browse/Search action inside the empty state, and no sign-in/sync entry. The audit did not create or remove a real bookmark.

![Step 20: Live Saved empty state](/Users/amosgodwin/WebstormProjects/law-padi/docs/ux-audit-2026-10-13/20-saved-empty.jpg)
