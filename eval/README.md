# Evaluation datasets

Versioned questions and expected answers used to measure retrieval and answer
quality. How they are used, the recorded results and the limits of the method
are in [`docs/evaluation.md`](../docs/evaluation.md).

| File pattern | What it is | Split |
| --- | --- | --- |
| `plain-language-retrieval-benchmark-v1.json` | 57 everyday questions about the Constitution with the section a reader expects first; results recorded under `baseline_2026_10_12` and `results_2026_10_17` | Development (the topic guide was tuned on it) |
| `plain-language-retrieval-heldout-v1.json` | 40 questions not used to write the topic guide | Held-out |
| `plain-language-retrieval-{benchmark,heldout}-{pcm,yo,ha,ig}-v1.json` | Draft translations of the two sets above, plus 10 native citation phrasings per language in the benchmark files | Same as the English source; `review_status: draft` |
| `statute-retrieval-{benchmark,heldout}-v1.json` | 7 provisional routing cases each for the ACJA 2015 and Police Act 2020 | Both are asserted in CI, so neither is a clean held-out set |
| `<law>-retrieval-benchmark.json` | One file per statute: queries with the one provision that best answers each, used for the Recall@10 gate on embedding runs | Model selection |
| `constitution-source-edition-benchmark.json` | 50 queries for the Constitution source edition | Review of the source edition |
| `constitution-explanation-evaluation-v1.json` | 203 English answer-evaluation cases with expected outcomes and paths; all pending human review | Answer gate |

Rules for these files:

- Do not add topic-guide phrases from a held-out file. If a held-out set is
  used to make a change, it becomes development data; write a new held-out set.
- A dataset version is immutable once results have been recorded against it;
  change the version suffix instead of editing cases.
- Some files are referenced by path. `plain-language-retrieval-benchmark-v1.json`
  is copied into the backend and Render images, hashed into the build revision
  (`scripts/build_revision.py`) and imported by the public methodology page
  (`frontend/src/lib/public-content.ts`). The statute routing sets are read by
  `backend/tests/legal/test_statute_retrieval.py`, and several scripts in
  `backend/scripts/` read the plain-language sets. Update those references when
  moving a file.
