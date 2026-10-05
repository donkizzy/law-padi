# Source formatting repair — 5 October 2026

Run: `b67bf7eb-1dd8-4a16-b09f-67271c4c0791`.

Source SHA-256:
`26c1b7f15fb6eae02aa2064e5cc2c3fa5d84f6c7c0b04a0f4e94a8183df3e838`.

## Applied changes

- Saved 1,778 audited revisions: 1,731 exact-character formatting/provenance
  repairs, 45 proven restorations of hyphens removed by the old line-wrap rule,
  one Schedule 3 boundary repair, and one visually verified table header repair
  on PDF page 138.
- Cleared 762 source-coverage findings through exact-character revalidation.
- Restored 27 Schedule 3 items (6–32) and six Schedule 7 oaths as new candidates
  with exact source-coordinate evidence. They remain awaiting review.
- Marked 13 misattributed Schedule 7 candidates rejected from the Constitution
  corpus. Their source, extraction text, issues, and decisions remain stored for
  separate instrument ingestion. The appendix begins on page 172 and includes
  the user's pages 191–234.
- Preserved the immutable original PDF and all existing candidate raw text.
  No candidates were approved and no corpus was published.

## Retained review findings

The user explicitly requested that source wording be preserved and malformed
punctuation flags remain open. Seven active Constitution candidates retain
punctuation blockers: Section 54 and its subsection 3, Section 188 and its
subsection 3, Section 305 and its subsection 1, and Schedule 1 Part II item 1.
These defects are present in the source, rather than introduced by the repair.

The numbering-gap diagnostic also remains open: the source prints `189.` where
the surrounding sequence runs from 167 to 169 on PDF pages 80–81. No inferred
renumbering was applied. Existing low-parser-confidence findings remain for
review. Findings attached to rejected appendix candidates are retained as audit
history, rather than waived.

The separate appended instruments have not yet been ingested under new legal
identities. The existing parser registry supports Constitution sources only;
separate ingestion requires supported parsers and reviewed instrument metadata.

## Validation

Ingestion extraction, normalization, parser, worker, and admin review regression
tests ran against a newly created disposable PostgreSQL database, preserving the
live review queue: **96 tests passed**. Backend Ruff, mypy, and ty checks passed.
The local review API also confirmed the restored oath and saved table revision.
Both local services now load extractor v2, normalizer v3, and parser v4. The
complete JSON audit is retained as run artifact
`artifacts/validation_report/source-formatting-repair-v2.json`.
The repair is also
versioned and reproducible through the maintenance command documented in
`ingestion-runbooks.md`.
