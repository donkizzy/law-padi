# Plan: add the ACJA 2015 and Police Act 2020 as verified sources

Status: 2026-10-20 — Phase 1 and the Phase 2–6 infrastructure are implemented. Qualified retrieval and prompt v11 answer contracts pass synthetic release tests; all 97 Constitution retrieval results are unchanged. Both real Acts remain in extraction review. Source verification, OCR/numbering acceptance and human review still block materialisation, composite publication and real statute evaluation. The Police Act expected count is corrected to 142 from its PDF arrangement. Phase 6 navigation, citations and public metadata pass synthetic multi-law checks; the actual public picker still lists only the Constitution. Phase 0 verification, actual activation and Phase 7 remain pending. See [ingestion evidence](statute-ingestion-progress-2026-10-19.md), [composite releases](statute-phase3-composite-release-2026-10-19.md), [Phase 4](statute-phase4-references-retrieval-2026-10-20.md), [Phase 5 validation](statute-phase5-answer-generation-2026-10-20.md) and [Phase 6](statute-phase6-frontend-2026-10-20.md).

Post-review corrections cover source cross-references, unknown state-law qualifiers, bare-reference scope, mixed-release ranking and phone topic hints. Complete Act title catalogues remain part of source acceptance. [Review fixes and validation](statute-review-fixes-2026-10-20.md).

## Why

Most of what users want to know about police searches, arrest and detention is in statute, not the Constitution. For example, police may search a person without a warrant only after arrest (ACJA), and on reasonable suspicion of stolen property (Police Act). Until those laws are verified sources, answers stop at "the Constitution protects privacy; a law may limit it".

## Decisions already made

| Decision | Choice |
|---|---|
| Source PDFs | Claude finds candidate official copies. **You approve each download** (source, file name, size) before anything is fetched. |
| Visibility | The Acts are **full peers** of the Constitution: their own Browse trees, a law picker in Find a section, and updated landing/SEO copy. |
| Status label | **"As enacted, may have been amended."** Answers never call either Act the current law, the same rule as for the 2004 Constitution edition. |
| Legal claims | Still come only from verified, published sources. The model never adds outside law. |

## What exists today

**Already multi-instrument:**
- `LegalInstrument` (with `InstrumentType.ACT`), `Provision.instrument_id`, `SourceDocument`, `CorpusRelease` and `CorpusReleaseEntry`. No new core tables are needed.
- Canonical paths are already prefixed by instrument slug (`constitution-1999.chapter4.section37`), so `acja-2015.part2.section9` won't collide.
- `instrument_parser.py` already defines an `InstrumentParser` plug-in boundary.

**Constitution-only by assumption (each must change):**
1. **Ingestion gates.** `ingestion/service.py:472`, `:2236` (`_get_or_create_constitution_instrument`), `legal/parser.py:90` and `legal/schemas.py:104` reject anything but a Constitution PDF. `instrument_parser.py` registers only `ConstitutionParser`.
2. **One release = one ingestion run = one instrument** (`ingestion/worker.py` `_run_release`, `_sync_release_entries`), and only one production release is allowed. A multi-law corpus needs a *composite* release.
3. **Bare section suffixes.** Six places match `".section9"` with `endswith` / `LIKE '%…'`, which would match both Constitution s.9 and ACJA s.9:
   - `legal/evidence.py:123`
   - `legal/public_corpus.py:249`
   - `chat/worker.py:467`
   - `chat/validation.py:84`
   - `ingestion/pgvector_repository.py:317` and `:326`
4. **Citations carry no instrument.** `PublicCorpus.citation()` and `ingestion/retrieval.py` `citation_for_provision()` produce `"Section 9"`. `EvidenceItem`, `LegalSearchResult` and `RetrievalSegment.citation` have no instrument fields.
5. **References.** `legal/references.py` rejects any "section X of the … Act" with "Law Padi covers Nigeria's Constitution only".
6. **Topic guide.** `legal/topics.py` uses bare section numbers ("37"), a Constitution-only titles file (`data/constitution-1999-section-titles.json`) and the `COMPANIONS` map. `related_laws` currently signposts these two Acts as *not included*.
7. **Answer layer.** The prompt (`chat/worker.py` `_SYSTEM`), notices, the edition notice and outcome copy all say "the Constitution".
8. **Frontend.** Constitution-only labels appear in about 15 files, including:
   - `BrowseConstitution.tsx`, `ProvisionView.tsx`, `SourcePanel.tsx`, `ChatHome.tsx`, `LandingPage.tsx`
   - `lib/seo.ts`, `lib/legal-provisions.ts`, `routes/_layout/constitution.index.tsx`

## Phases

Each phase ends green (tests, lint, retrieval benchmark) and is releasable on its own. Phase 1 changes no behaviour for users.

### Phase 0: Sources (small, needs you)
1. Find candidate official copies of both Acts: Federal Government gazette, Federal Ministry of Justice, or National Assembly. For each, report the URL, publisher, file name, size and page count, and **wait for your approval before downloading**.
2. Save each approved file into its own new folder as untrusted input. Record the SHA-256 and check the text layer (or flag it for OCR).
3. Check for amendments to each Act after enactment. If any exist, record them as `Amendment` rows for a later phase rather than mixing texts.
4. Register each as a `SourceDocument`: `SourceTier.OFFICIAL` for gazette copies, otherwise `TRUSTED_SECONDARY` with a note. Leave it `NEEDS_REVIEW` until you sign off.

**Done when** both PDFs are stored with hashes, provenance and your verification sign-off.

### Phase 1: Instrument-aware identity (medium, backend only, no UI change)
- **References.** Add an `instrument_slug` to `SectionReference`, defaulting to the Constitution so every existing call keeps working. `suffix` becomes a full path prefix (`f"{slug}.…section9"`).
- **Lookups.** Replace the six suffix matches with instrument-scoped matching through one helper (`legal/references.py` `matches_reference(path, ref)`).
- **Evidence fields.** Add `instrument_slug`, `instrument_title`, `instrument_short_title` and `instrument_type` to `EvidenceItem`, `LegalSearchResult` and `ProvisionReference`, filled from `LegalInstrument` in `PublicCorpus`.
- **Citations.** Keep `citation` exactly as it is for Constitution provisions (saved items and stored answers depend on it). Non-Constitution provisions get `"Section 9, ACJA 2015"`. Add a `short_citation` (`"ACJA s.9"`) for buttons.
- **Migration.** Add `instrument_id` to `RetrievalSegment` (backfilled from `provision`) so retrieval can filter or balance by law.
- **Tests.** Regression tests prove the Constitution's exact lookups, search and chat are unchanged. A fixture with a fake second instrument proves "Section 9" never matches across laws.

**Done when** the full suite, retrieval benchmark and Playwright pass with identical Constitution results.

### Phase 2: Act parsing and ingestion (large)
- **Act parser.** Add `ActParser` to `instrument_parser.py` (`instrument_types=("act",)`). It reuses the section, subsection and paragraph segmentation in `parser.py` (`_SECTION_RE`, `_subsection_segments`, `_paragraph_segments`), handles Parts without Chapters, marginal or inline section headings, interpretation sections, Schedules and Roman-numeral clauses, and takes headings from each Act's "Arrangement of Sections".
- **Lift the gates.** Allow `InstrumentType.ACT` in the four places above, behind an allowlist setting (`INGESTION_ALLOWED_INSTRUMENT_TYPES`). Generalise `_get_or_create_constitution_instrument` to `_get_or_create_instrument`.
- **Section titles.** Make section titles per instrument (`data/<slug>-section-titles.json`), and make `section_title()` take the instrument.
- **Status.** Store Act provision versions with the "historical" status semantics and an edition label such as "As enacted, 2015". This reuses the existing guard that stops answers calling text current law.
- **Golden tests.** Add golden-PDF tests in `tests/ingestion/test_golden_pdfs.py` for both Acts: section count matches the Arrangement of Sections, plus spot-checked text for key sections (ACJA search and arrest provisions, Police Act search provisions).
- **Review.** Run both Acts through the existing extraction review and approval workflow. You (or a lawyer) spot-check the parsed text against the PDFs.

**Done when** each Act has an approved, materialised ingestion run with zero blocking review issues.

### Phase 3: Composite release (medium)
- **Composing.** Add an admin action, "Compose release", that creates a new `CorpusRelease` whose entries are the union of the current production Constitution release and each approved Act release. Record the member release IDs and source hashes in `validation_report`.
- **Gates.** Extend `_release_source_and_review_gates` to check every member instrument.
- **Index.** Build segments and embeddings for the new release, reusing vectors whose `retrieval_text_sha256` is unchanged if the embedding store supports it (to check); otherwise re-embed (about 2,500 segments, a low cost). Then validate the index and promote through the existing approval flow.
- **Existing conversations** stay pinned to their old release (`Conversation.pinned_release_id`). New conversations use the composite release.

**Done when** the composite release is production locally with checksums validated and no Constitution regressions.

### Phase 4: References, topics and retrieval (medium)
- **References.** `references.py` parses instrument-qualified references using an alias table: "ACJA", "Administration of Criminal Justice Act", "ACJ Act", "Police Act", "Nigeria Police Act", plus forms like "section 9 of the ACJA", "ACJA s.9" and "s.29 Police Act". Unknown laws are still rejected, with copy that lists the covered laws.
- **Topics.**
  - Topic targets become instrument-qualified (`"constitution-1999:37"`, `"acja-2015:9"`).
  - New statute topics: search of an arrested person, arrest without warrant, stop and search, bail, time limits for detention, recording of statements, police powers to search premises.
  - Cross-law companions: for example, Constitution 35 pairs with the ACJA arrest and detention sections.
  - Remove ingested laws from `related_laws`.
- **Ranking.** For rights questions, keep the Constitution provision first and Act provisions as detail. Raise semantic `top_k` from 5 to 6, with at most 3 sections per instrument so one Act can't crowd out the Constitution.
- **Benchmark.** `expected_sections` become instrument-qualified. Add statute cases and statute held-out cases. The existing Constitution scores must not drop.

### Phase 5: Answer generation (medium)
- **Prompt v11:**
  - Answer from all supplied laws.
  - Name the law when citing ("Section 9 of the ACJA").
  - The Constitution is supreme: describe Act powers as operating within constitutional rights.
  - Jurisdiction caveat: the ACJA governs federal courts and the FCT, and many states have their own Administration of Criminal Justice Laws. Mention this only when it changes the answer, and add "Which state you are in" to `missing_facts`.
  - "As enacted" wording rules for the Acts.
- **Validation.** `chat/validation.py` citation checks become instrument-aware: a block may cite "Section 9 of the ACJA" only if ACJA s.9 is in its evidence. The verifier prompt is updated the same way.
- **Notices.** Edition notices are per instrument, and the "not covered" and "no match" copy names the covered laws.
- **Examples.** The phone-search question should now be able to say when police may search without a warrant, with ACJA and Police Act citations, Section 45 limits and Section 46 remedies.

### Phase 6: Frontend as full peers (large)
- **Instruments endpoint.** Add `GET /api/v1/legal/instruments` (slug, titles, edition label and note, section count) and regenerate the client (`bash scripts/generate-client.sh`).
- **Browse.** Add a law switcher. The tree endpoint takes `instrument`. Routes become `/laws/<slug>/…`, and `/constitution` keeps working as an alias so shared links don't break.
- **Find a section.** Add a law picker and accept "ACJA s.9" typed directly.
- **Section labels.** Chips, cards, the source panel, saved items and exports show the law (`short_citation` on chips, full citation on cards). Each law gets its own edition caveat.
- **Copy and SEO.** Update landing, SEO and meta copy in `lib/seo.ts`, `LandingPage.tsx` and `public-content.ts`, e.g. "Nigeria's Constitution and key laws". Keep the constitution.ng brand and logo.
- **Design system.** Follow the project design system (the design system canvas, tokens in `frontend/src/index.css`).
- **Tests.** Playwright covers the law switcher, an Act section detail page, an ACJA citation in an answer, saved items and the legacy `/constitution` links.

### Phase 7: Evaluation and rollout (medium, needs a reviewer)
- Add gold provisions for both Acts, and add statute answer cases to `docs/constitution-explanation-evaluation-v1.json` (or a new `statute-explanation-evaluation-v1.json`): police search, arrest without a warrant, bail, detention limits, the phone question.
- Get human review of a sample of answers (ideally a Nigerian lawyer) before turning it on in production. This uses the existing `review_status` flow.
- Roll out:
  1. compose and publish locally
  2. staging
  3. production
  Keep the Constitution-only release as the rollback target.

## Order and parallelism
- Phase 0 and Phase 1 can run at the same time.
- Phase 2 needs the PDFs from Phase 0.
- Phase 3 needs Phases 1 and 2.
- Phases 4 and 5 need Phase 3, and can mostly run in parallel because they touch different files.
- Phase 6 can start on the instruments endpoint and switcher after Phase 1, with real data after Phase 3.

## Risks
- **Currency.** Either Act may have been amended. The "as enacted" label and the check in Phase 0 step 3 cover this; adding amendments is later work.
- **State laws.** For many state offences, a state's ACJL applies rather than the federal ACJA. The jurisdiction caveat handles this, and adding Lagos and other state laws is later work.
- **Parser quality.** Acts are formatted differently from the Constitution. Golden tests plus human review gate publication.
- **Regressions from cross-law matching.** Phase 1 exists specifically to remove the suffix-matching ambiguity, with tests first.
- **Cost and latency.** More evidence means more prompt tokens: roughly +20–30% per answer at today's prices. Answers already take 30–80 seconds with thinking on.
- **Scope of the brand.** Moving to "Constitution and key laws" changes how the product is positioned. The copy changes are isolated in Phase 6.
