# 0003. English core, translated edges

Status: accepted. In place since 20 October 2026; non-English answers are
labelled Beta pending native-speaker review.

## Context

Readers ask in English, Nigerian Pidgin, Yorùbá, Hausa and Igbo. The legal
texts are in English. Running retrieval, drafting and validation separately per
language would multiply the surface that has to be evaluated, and the
deterministic citation checks depend on English section and law names.

## Decision

Translate only at the edges (`backend/app/chat/translation.py`):

- A question that is not clearly English gets one budgeted call that returns
  its language and an English rendering. Retrieval, drafting, deterministic
  validation and the verifier run on the English text.
- The verified English answer is translated with a per-answer glossary slice
  (`backend/app/languages/data/`), then checked deterministically: numbers, law
  names, list items and quotation marks preserved, a plausible length ratio, and
  no text left in English. Yorùbá, Hausa and Igbo also go through a
  back-translation judge.
- Any failure returns the English answer. Official wording is always shown in
  English. Section, Act and similar terms are locked to their English form so
  citations stay checkable.

## Consequences

- One retrieval and validation path to evaluate; the languages add measurable
  translation steps rather than separate pipelines.
- A non-English answer costs extra calls (understanding, translation and, for
  three languages, judging), all reserved in the spend ledger.
- Translation quality is not established: glossaries, translated benchmarks and
  interface catalogues are unreviewed drafts. The enable gates are in
  [multilingual-evaluation-plan.md](../multilingual-evaluation-plan.md); the
  human review that removes the Beta label is in
  [reader-language-review-checklist.md](../reader-language-review-checklist.md).
