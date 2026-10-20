# Phase 5: multi-law answer generation

Prompt `constitution-english-v11`, instrument-aware validation and per-law notices are implemented. Synthetic releases exercise the Constitution, ACJA 2015 and Police Act 2020 together. **Neither real Act is verified, materialised or published.** Live statute-answer accuracy and human legal review remain pending. [Local preflight](statute-phase5-local-preflight-2026-10-20.json).

## Answer and verification rules

The generator now answers from all supplied published provisions. Each evidence row carries its canonical path, instrument identity and edition. `covered_laws` describes the selected release's availability; it cannot supply a legal rule. Identical text in different laws remains separate in the prompt.

The prompt requires named Act citations, such as `Section 9 of the ACJA`. Bare section numbers continue to mean the Constitution. It considers supplied Act powers and safeguards alongside Constitution rights before choosing yes, no or depends; it no longer assumes that privacy alone resolves every phone-search or refusal question.

When Acts participate, context reserves two additional slots for published Constitution s.1 and ACJA s.2 as applicable, alongside relevant rights, limits and remedies. This also works when an Act first enters as a companion to a Constitution provision. Missing and unpublished provisions are never manufactured. Context stays release pinned, and the existing prompt-size limit still applies.

Jurisdiction guidance must follow the supplied application provision. The prompt avoids assuming nationwide ACJA application, keeps location-dependent claims conditional and asks **“Which state you are in”** when that fact changes the answer. An abstract provision explanation need not ask for location. State criminal-procedure rules cannot come from model knowledge; affirmative claims still require cited evidence.

The verifier receives the same identity, availability, prior user context and missing facts. It checks Act/Constitution relationships, jurisdiction qualifications and historical status. These are model-assisted semantic checks; scripted-provider tests do not establish live-model legal accuracy.

## Citation and edition checks

An Act citation requires the correct canonical section or its containing hierarchy in that block's cited evidence. A same-numbered section of another law, an uncited item elsewhere in the answer or a bare cross-reference in another Act section cannot support it. Named laws and enactment years are checked even without a section marker.

The legacy Constitution source-cross-reference allowance remains, with parsed identities replacing substring matching: a source mention of s.99 cannot support s.9. An unqualified current-law claim is rejected when any cited item is historical, including mixed historical/current evidence. The status check also catches “in force”.

Act results say **“As enacted, may have been amended.”** Constitution results in a composite retain their frozen member's edition. Successful answers show one caveat per law actually cited in retained blocks, preserving the existing Constitution caveat.

No-match, not-covered and failure notices name the laws in the selected release. The chat UI displays these server notices instead of Constitution-only replacements, preserves separate edition paragraphs and shows per-law caveats when an explanation is withheld. Older responses retain a fallback. Browse, the law picker and broader product copy remain Phase 6 work.

## Validation

- Backend: **620 passed, 4 skipped**, **89% coverage**; mypy, ty and Ruff lint/format pass. Eighteen new synthetic answer cases cover correct/wrong laws, currency, scope context, editions, missing coverage and the phone-search flow.
- The synthetic phone case passes generation and both validation stages with both Acts, Constitution limits and a remedy, plus application-scope evidence and missing location facts. It uses a scripted provider and explicitly synthetic source clauses.
- Frontend build and Biome pass. Admin, legal-home and chat suites pass **53 browser tests**. The two notice cases were rechecked after clearly labelling Act fixture text as synthetic. An earlier attempt stopped at login during an automatic local API rebuild; the subsequent full run passed.
- All **97 Constitution retrieval results** match Phase 4. The fourteen provisional real-statute retrieval cases remain blocked on publication. [Retrieval comparison](statute-phase5-retrieval-validation-2026-10-20.json).
- All **90 deterministic citation-identity checks** in the existing 200-case explanation dataset pass. Case e185 now expects an unavailable Police Act in its pinned Constitution-only release, rather than an unrecognised law. Human grounding judgments remain pending. [Identity checks](statute-phase5-explanation-identities-2026-10-20.json).

The active release remains `draft-c8d50d87fae9`, with 1,829 segments and embeddings and unchanged checksums. No source approval, Act materialisation, composite publication or live language-model call was performed. Retrieval benchmarks used the configured query-embedding provider; those calls are separate from answer generation.

Complete source/amendment verification, OCR correction and extraction approval before activating the real Acts. Prompt v11 requires fresh live captures and human grounding review before rollout; earlier prompt evaluations do not certify it. [Validation summary](statute-phase5-validation-2026-10-20.json). The browser screenshot used synthetic fixtures and confirmed presentation only; it was removed at the user's request on 20 October 2026.
