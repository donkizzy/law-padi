# Phase 4: law-qualified references and retrieval

References, topic routing and mixed-law ranking are implemented. Synthetic published releases exercise the Constitution alongside both Acts. **Real statute retrieval remains pending source verification, corrected extraction and publication.** The application still serves the existing Constitution release; neither real Act has canonical versions or an approved member release. [Local preflight](statute-phase4-local-preflight-2026-10-20.json).

## References and release boundaries

The parser recognises ACJA, Administration of Criminal Justice Act, ACJ Act, Police Act and Nigeria Police Act, with their enactment years. It accepts forms including `section 9 of the ACJA`, `ACJA s.9`, `Section 9, ACJA 2015` and `s.29 Police Act`. Lists and bounded ranges preserve law identity. Adjacent conjoined markers inherit that law; an explicit qualifier overrides inherited scope, and a sentence boundary resets it. Bare references continue to mean the Constitution.

Unknown laws, conflicting qualifiers, wrong years and differently named Police Acts are rejected. Recognition grants no access to unpublished material. A recognised Act absent from the selected edition gets a missing-law message; an absent section of a present Act gets a missing-section message. Exact evidence and citations remain canonical and release scoped.

Source cross-references use their source instrument as the default while respecting explicit names of other laws. Subsection follow-ups retain the preceding law. Two same-numbered sections from different laws remain distinct and require clarification when a follow-up is ambiguous.

## Topics and ranking

Topic and companion targets now use `instrument-slug:section`. Statute navigation hints cover arrested-person search, warrantless arrest, stop and search, bail, detention, statements and premises searches. Per-law section-title catalogues participate only for instruments present in the selected release. The catalogues remain provisional navigation metadata, not approved legal wording.

Constitution rights provisions have cross-law companions, and statute provisions can bring Constitution context into an explanation. Companion reads remain pinned to the selected release. Related-law signposts remove an Act only when that same release actually includes it; draft registration alone changes no coverage claim.

Chat semantic retrieval requests six sections. In a mixed release, fusion selects at most three sections per instrument and puts the matching Constitution rights result first for rights questions. The same policy applies to lexical fallback and benchmark fusion. A single-instrument release keeps its existing ranking without a three-result cap, preserving Constitution-only recall. Results are deduplicated by qualified section identity, and noise demotion affects only the named Constitution sections.

## Evaluation

The two Constitution datasets now use qualified expected references; their queries and expected provisions are unchanged. All metrics and miss rankings match Phase 3 after identifier qualification across **97 cases**. Fused hit@1/hit@5 remains **0.98/1.00** on the 57-case dataset and **0.95/1.00** on the 40-case held-out dataset. [Benchmark comparison](statute-phase4-retrieval-validation-2026-10-20.json).

There are seven provisional statute cases and seven held-out cases. Synthetic routing checks pass for all fourteen. The real benchmark runner reports these datasets as blocked before requesting embeddings because the active release lacks both Acts. These checks do not establish semantic retrieval quality or lawyer-approved answer accuracy on the real statutes.

The backend suite passes **602 tests**, with four skips and **89% coverage**. Mypy, ty, Ruff lint/format, frontend build and Biome pass. Existing admin and legal-home Playwright suites pass **36 tests**, with no retry needed. Public API schemas are unchanged. [Validation summary](statute-phase4-validation-2026-10-20.json).

## Source-count correction and remaining work

Inspection of the retained Police Act PDF's arrangement on **PDF page 4** shows **142. Citation**, followed by the Schedule. The navigation catalogue and optional full-PDF acceptance check now expect **142 sections**, correcting the earlier expectation of 145. The original PDF hash is unchanged. Earlier Phase 2 reports retain their dated findings and expectations.

Reparsing the existing OCR still fails reconciliation: ACJA has 594 section candidates against 495 expected, with 57 missing expected numbers; the Police Act has 131 candidates against 142 expected, with 21 missing expected numbers. Repeated and unexpected numbers also remain. No new OCR, review approval or canonical materialisation was performed. [Source recheck](statute-phase4-source-checks-2026-10-20.json).

The active release remains `draft-c8d50d87fae9`, with 1,829 segments and embeddings and unchanged checksums. Complete source/amendment verification, OCR correction, extraction approval and composite publication before measuring actual mixed-law retrieval. Phase 5 answer prompts and notices, Phase 6 frontend law navigation and Phase 7 human evaluation remain outstanding.
