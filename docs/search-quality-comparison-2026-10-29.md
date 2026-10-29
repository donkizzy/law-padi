# Search quality vs a general-purpose Claude, 2026-10-29

Scope: the whole active release (Constitution 1999, ACJA 2015, Police Act 2020), 100 realistic questions in `docs/claude-comparison-queries-v2.json` (the `truth` notes there are the writer's recollection and are unverified; grading used the stored provision text).

Method: Claude answered blind (no corpus, no tools). The app answered through the real chat path (hybrid retrieval, deepseek-flash, prompt v11) on an isolated clone of the production database. Five independent graders scored both answers against the stored text of the cited provisions: accuracy, helpfulness and citation 0-2, plus listed factual errors. Live spend was under US$1.

## Before the fixes

| | App | Claude |
|---|---|---|
| Directly answered (helpfulness 2) | 47 | 90 |
| Accuracy 2 | 55 | 76 |
| Winner (app/claude/tie) | 20 | 51 / 29 tie |

Only 57 of 100 returned an explanation: 24 were refused as "too large" (an evidence-size gate), 11 failed the verifier ("opening block did not answer the question", usually because retrieval had missed a companion section such as s.137), 8 were insufficient evidence.

Causes of app losses: gave up 20, retrieval miss 12, validation failure 10, drafting 7, corpus gap 6.

## Changes

- `app/chat/worker.py`: an oversized evidence packet is now trimmed (context first, then the lowest-ranked matches, never the best match) instead of refusing the question.
- `app/legal/topics.py`: about 25 subject topics for the Acts and uncovered Constitution subjects (bail for capital offences, plea bargain, remand, bail forfeiture, child suspects, police complaints, election disputes, community policing, governor immunity phrasing, term limits, military takeover and others) plus conservative typo repair against the guide's vocabulary.
- Tests: `tests/legal/test_topics.py`, `tests/chat/test_evidence_fit.py`.

## After the fixes (same 100 questions, re-run on the 43 that previously had no explanation)

| | App | Claude |
|---|---|---|
| Directly answered | 74 | 90 |
| Accuracy (mean 0-2) | 1.76 | 1.76 |
| Winner | 31 | 30 / 39 tie |

87 of 100 now return an explanation. The 13 left are 8 insufficient evidence (mostly correct: nonexistent sections and questions outside these laws) and 5 validation failures.

Retrieval on a held-out set written after the fixes (`docs/claude-comparison-heldout-v3.json`, 40 questions): expected section in the top 5 went from 35 to 36 of 40, and first from 21 to 21. The topic additions do not generalise on their own; the dev-set gain (top 5: 81 to 91 of 95) is partly tuning. Existing benchmarks are unchanged (98% / 97% top-1).

## Caveats

- Graders are Claude models, and the baseline is Claude, so some self-preference is possible.
- Ground truth is the stored as-enacted text. Claude was marked down where it stated later amendments (for example presidential minimum age 35, House 25 after 2018). That is current law and the app is not. Currency, not accuracy, is the product risk here.
- Cases that already completed before the fixes were not re-run; they keep their original grades although the topic changes could affect them.

## Second round: the open issues

- Companion context was being lost. My first trimming dropped context from the end, which discarded s.45/s.46 and the Act companions while keeping parent sections. Trimming now drops the lowest-ranked matches first (keeping four), then context, and `CHAT_EVIDENCE_MAX_CHARS` defaults to 36,000. Verified: the speech and religion questions now load s.45/s.46, the court-papers question loads s.36, and s.135 now brings in s.137 (the president-term question completes).
- Statute subjects: every Part of ACJA and the Police Act now has plain-language subject coverage (`_PART_TOPICS` in `app/legal/topics.py`: remand, speedy trial, mental incapacity, sentencing, victim compensation, probation, death sentence, witnesses, warrants, traffic wardens, special constables, gender equality, lost property and others).
- Padded sources: a delivered explanation now lists only the sections it cited or was asked about (`_shown_evidence`).
- Re-run of the 18 hardest cases on the final code: 14 completed (including 12 that had been unanswered or weak), 2 insufficient evidence (one is correct: the child-suspect provision defers to the Child's Rights Act, which is not in these three laws), 2 verifier rejections.
- Benchmarks after all changes: v1 98% / held-out 97% top-1 (unchanged); full backend suite 758 passed; ruff and mypy clean.

## Still open

1. "How many years can a president stay in power" still fails the strict verifier even with s.135 and s.137 loaded. It is left failing closed rather than loosening verification.
2. Out-of-scope questions still use the shared "closest sections we found" wording. The misleading "too broad" label is gone (it was the size gate), but the copy lives in the search path, the English locale catalogue and Playwright specs, so I did not change it without running the browser tests.
3. The corpus is the as-enacted text. Claude states later amendments the app does not have (presidential minimum age 35, House 25). Closing this needs the amendments ingested and reviewed; no retrieval change can fix it.
4. Part-level topics were written after the held-out set, so that set no longer measures generalisation. A new held-out set is needed before the next claim about unseen phrasing.
