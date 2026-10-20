# Response to Claude's implementation review

Claude's main finding was correct: parsing an entire provision as one strict reference input caused valid source cross-references to disappear. The earlier 97-case benchmark measured search ranking, not chat evidence assembly, and could not establish that the latter was unchanged. This review adds separate source-context checks and a mixed-release retrieval check.

## Findings and disposition

| Finding | Result |
|---|---|
| 1. Lost Constitution/source cross-references | Confirmed and fixed. Source groups are checked independently. Unsupported references do not erase other groups. `this Act` uses the source/selected Act; explicit named laws retain their own identity. The worker prioritises one reference from each marker before filling spare slots from long lists, so Section 45's opening list cannot consume all five slots. Answer validation shares the source-reference helper for the existing Constitution cross-reference allowance. User queries and generated answer citations still fail as a whole on unsupported citations. |
| 2. Lagos ACJL fallback and Nigerian Police Act alias | Confirmed and fixed for the supported reference forms. Unknown ACJL/state criminal-procedure law qualifiers return an unsupported-law result instead of becoming Constitution references. Both “Nigeria Police Act” and “Nigerian Police Act” are recognised. Recognition continues to require published release membership before serving text. |
| 3. Bare references inheriting the preceding Act | Confirmed and fixed. Each new section marker starts with the supplied default law: Constitution for answer validation, or the law explicitly selected in Find. A list/range under one marker retains its named law. Thus `section 9 of the ACJA and section 35` means ACJA 9 plus Constitution 35, while `ACJA sections 9 and 10` stays within ACJA. |
| 4. Mixed-law truncation and unrelated rights promotion | Confirmed and fixed. Publishing Acts no longer caps Constitution results at three or truncates a single-law candidate pool. Act diversity is a preference with a sparse-result fallback. First-place Constitution promotion requires an actual query topic/title match already inside the requested result window; a section number between 33 and 46 is insufficient. All 97 Constitution cases were measured in an isolated mixed-law database. |
| 5. Partial Act title catalogues | Confirmed; the complete source catalogue work remains pending. Public results now fall back to stored Act arrangement headings, including the parent section heading for a subsection. This removes the partial navigation catalogue as the sole display-title source. It does **not** fabricate or approve missing headings. Complete arrangement/body reconciliation and checked title catalogues remain publication prerequisites. |
| 6. Phone question missing Act topics | Confirmed and fixed. Phone-search/unlock phrasing now has ACJA 9 and Police Act 49 topic hints alongside Constitution privacy hints. Hints are still filtered by the selected release and supply no legal wording or approval. |

The production budget edits in `render.yaml` and `deployment/render/prepare_env.py`, and the staged deletion of `docs/ux-audit-2026-10-13/`, were already present in the workspace before Phase 6. This review did not change, stage, approve or deploy them.

## Evidence and limits

The new regressions first reproduced nine failures, including source Section 45, Lagos ACJL and mixed named/bare reference validation. The final full backend run passes **645 tests, 4 skipped, 89% coverage**. Mypy, ty, Ruff lint and formatting pass, including the changed tests and evaluation utility. Eighteen net new cases were added. No frontend code or API schema changed in this review, so the browser suites were not rerun for these backend fixes; the Phase 6 browser record remains separately dated and scoped.

The source audit reads only full Constitution SECTION rows from the selected production release. It compares the legacy marker identities, with the legacy five-reference limit, against the repaired extractor. This method found 63 sections with markers and 11 with missing identities before the fix; it is narrower than Claude's reported 70-section sample. After repair there are **zero missing previously resolvable references**. One legacy regex artifact, `section218o`, came from the source string `218of` and has no canonical provision; the strict boundary check continues to reject it instead of changing source text or guessing a section number. [Source-context audit](statute-review-crossrefs-2026-10-20.json).

The actual read-only `_context` call for published Section 45 now includes:

- Constitution 37;
- Constitution 33;
- Constitution 36(8);
- Constitution 305;
- Constitution 38, using the spare slot from its opening list.

A frozen Section 45 test fixture records the source ID, page and text hash. Tests also cover unsupported references alongside valid references, relative `this Act` references, and references followed by a new paragraph.

`backend/scripts/check_mixed_law_retrieval.py` performs a separate retrieval check. It reads the actual active Constitution index in a read-only transaction, creates a uniquely named disposable `_test` database, applies migrations and copies the Constitution corpus/index. It measures the two existing datasets, adds 41 explicitly synthetic Act provisions, then measures the same queries with replayed query vectors. Act vectors are copies of Constitution privacy/liberty vectors to stress crowding; these are not embeddings or a legal-accuracy evaluation of the real Acts. Only the newly created database is dropped, in a `finally` block. Its successful removal is recorded in the report. The application database and ordinary test database are not mutated by this utility.

| Dataset | Cases | Fused hit@1 before/after | Fused hit@5 before/after | Fused MRR before/after |
|---|---:|---:|---:|---:|
| Constitution benchmark | 57 | 0.98 / 0.98 | 1.00 / 1.00 | 0.99 / 0.99 |
| Constitution held out | 40 | 0.95 / 0.95 | 1.00 / 1.00 | 0.96 / 0.96 |

Fallback metrics also remain unchanged. These are aggregate metric comparisons; mixed membership can change candidate signals and individual rankings. An initial mixed run caught an unlock-phone ranking regression, which was corrected before the passing rerun. This additional synthetic check does not replace evaluation against the eventual approved, complete Act corpus. [Mixed-law comparison](statute-review-mixed-retrieval-2026-10-20.json).

The final preflight confirms the real public release remains Constitution-only: both Acts are still `needs_review`, with no materialised versions or approved member releases. The active index still has **1,829 segments and embeddings** and unchanged checksums. No canonical legal wording, source approval, application publication, production budget, deployment or dependency lockfile was changed. No live language-model calls were made. The mixed-law benchmark used the configured query-embedding provider, with the same vectors replayed between its baseline and mixed measurements. [Local preflight](statute-review-local-preflight-2026-10-20.json).

Complete and verify the source catalogues and OCR, resolve amendment provenance, approve extraction, and repeat retrieval/answer evaluation against the real composite before activation. Those review gates remain in force.
