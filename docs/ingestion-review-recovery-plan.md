# Constitution ingestion recovery — 5 October 2026

## Agreed scope

Complete local development run `c8d50d87-fae9-4538-af68-d6de4de1ce77`
through indexing and validation, then stop for the user's release approval.
Ingest the historical/source edition of the Constitution from the uploaded PDF.
Preserve wording and both printed Section 189 identities; document the absent
Section 168. Retain appended instruments for later separate ingestion. Paid
embedding calls are authorized. Source-verified extraction and structure may be
approved; substantive ambiguities require the user's decision.

## Verified baseline

The read-only inventory is in `ingestion-review-audit-2026-10-05.json`.

| Item | Count or status |
| --- | --- |
| Candidates requiring approval | 1,851 |
| Text-bearing candidates | 1,811 |
| Low-parser-confidence findings | 136 |
| Numbering-gap findings | 1 |
| Blocking punctuation findings | 7 |
| Text matching stored coordinate spans character-for-character, excluding whitespace | 1,811 |
| Missing parents / child text outside its parent | 0 / 0 |
| Missing section number | 168 |
| Repeated section number | 189, on PDF pages 80 and 88 |
| Source verification | Needs review |
| Active embedding profiles / evaluation datasets | 0 / 0 |

The UI's 100 count is a first-page count, not the complete backlog. The 136
confidence findings comprise 91 paragraphs, 43 schedule items and two sections.
All have score 0.78: the parser assigns this score to short text. Character
agreement establishes extraction consistency, not independent legal accuracy.

The seven punctuation blockers concern four source passages: Section 54(3),
Section 188(3), Section 305(1), and Schedule 1 Part II item 1. The first three
also appear on their parent sections. PDF pages 44, 87, 124 and 138 visually
confirm the defects. Page 80 visually confirms printed 189 after 167. Page 172
contains the end of the Judicial Oath and the start of separate Fundamental
Rights Rules. The Constitution parser stops at that boundary.

The earlier formatting report describes a different run, not this current run.
The live run has zero candidate revisions and uses parser v4/normalizer v3.

## Execution sequence and acceptance gates

1. Preserve the original PDF, export a complete issue/candidate manifest, and
   reproduce coordinate evidence from the original PDF. Fail closed if a
   candidate's text, coordinates, parent, or optimistic version changes.
2. Treat the corpus as historical during materialization and retrieval export.
   Test that historical versions cannot overwrite current law and that only
   this edition enters its release. Existing current-law behavior stays covered.
3. Resolve low-confidence findings only after exact source and hierarchy checks.
   Record individual reasons and evidence. Resolve source punctuation and
   numbering findings as explicitly authorized source-preserving exceptions,
   retaining original wording, printed numbers, page evidence and audit records.
   No inferred Section 168 is created. Parent/child findings share the same
   underlying source exception but retain separate review records.
4. Approve all eligible candidates through normal review services using
   idempotency keys and optimistic versions. Verify the original PDF as a
   historical source compilation; this does not certify it as current amended
   law. Keep appendix content outside the Constitution candidates.
5. Correct the configured Hugging Face URL from sentence similarity to feature
   extraction. Preflight returned one 1,024-dimensional vector. Configure the
   BAAI/bge-m3 profile with recorded model revision and a versioned retrieval
   benchmark containing independently authored queries and expected paths.
   Do not make a gold extraction set by copying candidates and use it to claim
   independent legal-grade accuracy.
6. Materialize, build retrieval documents, embed in bounded batches, build
   pgvector and validate counts, hashes, dimensions and provenance joins. Apply
   the existing Recall@10 >= 0.95 gate without weakening it. Diagnose failures
   rather than changing expected answers to make the gate pass.
   Persist content-addressed batch checkpoints so provider failures resume from
   completed work. Cache identity includes input text, position, profile,
   provider, revision, dimensions and configuration. Verify checkpoint hashes
   before reuse and retain individual progress counts. Report provider failures
   separately from failed quality benchmarks.
7. Stop at `ready_to_publish`. Verify zero open findings, all in-scope candidates
   materialized, historical status in index payloads, a ready index, no active
   production target, and publication still pending. Save outcome metrics and
   unresolved limitations for the user's release review.

## Tests and known workflow follow-ups

Run materialization, review and index regression tests against a disposable
database. The repository's test fixtures delete legal tables, so tests must
never run against the live review database. Run backend type/format checks and
frontend build checks if the queue UI is changed.

The existing review/materialization/publication gates treat rejected candidates
as unfinished. The current run has no rejected candidates, so that defect is
not a blocker here. A future exclusion workflow needs explicit terminal rejection
handling, checks for accepted children of rejected parents, and coverage gates.

The historical edition contains source typos and wording anomalies beyond
punctuation. Acceptance means faithful preservation of this edition, not a
corrected or current consolidated Constitution. Missing Section 168 and duplicate
printed 189 must remain visible in release review. Hugging Face serverless model
revision metadata does not by itself prove provider-side revision pinning; retain
the actual vectors and checksums and document that limitation.

## Execution record

All 1,851 candidates passed original-PDF structure, text and coordinate replay.
All 144 findings have individual documented resolutions; source wording was not
revised. All candidates materialized, producing 1,811 historical text versions
and 1,829 retrieval documents. The UI now paginates the actual queue and retains
source-edition evidence on the release review page.

The initial embedding attempt failed after a roughly 60-second request gap.
The immediate automatic retry cleared its provider error, so the precise
original exception could not be recovered. This was a provider-stage failure,
not an observed Recall@10 failure: no benchmark score had been recorded.
The worker was stopped, durable batch recovery and explicit provider error
reporting were tested, its stopped lease was released with an audit record,
and the same task resumed with a 120-second request timeout. The earlier
in-memory batches could not be recovered. Final index evidence will be recorded
in a separate completion report after the unchanged quality gate passes.

The run subsequently completed embedding with Recall@10 0.98 across 50 queries
and passed pgvector validation with 1,829 segments and vectors. It is now
`ready_to_publish`; approval and publication remain pending. See
[the completion report](ingestion-review-completion-report.md) and its evidence
for final counts, checks, source exceptions and limitations.
