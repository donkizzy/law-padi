# 0002. Answers cite supplied evidence; citations come from the server

Status: accepted. In place since the first generated explanations (October 2026).

## Context

A wrong legal citation or an invented provision is the most damaging error the
product can make. Language models produce plausible citations and paraphrase
text as if it were current law. The source editions used are historical (the
Constitution compilation predates later alterations, and the Acts are as
enacted), so "this is the law today" is itself a claim to guard against.

## Decision

- Citations, edition labels and source links are generated from structured
  metadata (`backend/app/legal/evidence.py`), never taken from model text.
- The model receives numbered evidence items and must attach evidence IDs to
  every answer block.
- A deterministic validator (`backend/app/chat/validation.py`) runs first. It
  rejects a block that cites unsupplied evidence, quotes wording absent from its
  cited text, cites a section or names a law outside its evidence, describes how
  it was produced, or calls historical text current law.
- A separate model verifier then reviews each block, and its output is
  shape-checked.
- A failing first block rejects the answer; failing later blocks are dropped.
  Any provider, schema or validation failure withholds the explanation and
  shows the source wording instead. Draft text is never streamed.
- When text is served, its hash is recomputed and compared with the stored
  hash.

## Consequences

- A reader never sees an explanation that failed either check; the cost is a
  higher rate of withheld answers.
- Retrieval quality bounds answer quality: if a needed companion section is not
  retrieved, a correct answer cannot pass validation.
- The verifier is a model and is a risk reduction, not legal certification.
  Grounding quality still needs human review
  ([evidence-chat-rollout.md](../evidence-chat-rollout.md)).
