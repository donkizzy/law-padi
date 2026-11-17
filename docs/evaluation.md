# Evaluation

How retrieval and answers are measured, what the numbers are, and how far they
can be trusted. Every figure below is quoted from a file in this repository,
named next to it. The datasets live in [`eval/datasets/`](../eval/datasets/);
[`eval/README.md`](../eval/README.md) lists them.

## What is and is not checked automatically

| Check | How it runs | Gated in CI |
| --- | --- | --- |
| Backend unit and integration tests, including deterministic answer validation, budget reservation and topic routing | `backend/scripts/test.sh` in the Test Backend workflow, 87% floor with branch coverage on `backend/app` | Yes |
| Topic routing for the 14 provisional statute cases (`statute-retrieval-benchmark-v1.json`, `statute-retrieval-heldout-v1.json`) against a synthetic release | `backend/tests/legal/test_statute_retrieval.py` | Yes (every development case must hit; the held-out cases are held to a floor of 6 of 7) |
| Offline ranking over synthetic heading-based text: lexical and topic ranking fused as in production, no embeddings (hit@1, hit@5, MRR@10) | `backend/tests/legal/test_retrieval_quality.py` against the floors in `eval/baselines/retrieval.json` (measured: development 1.00 on 57 questions; held-out hit@1 0.90, hit@5 0.975 on 40) | Yes |
| Section-level retrieval quality with dense search (hit@1, hit@5, MRR) | `backend/scripts/retrieval_benchmark.py` against a live database and the query-embedding endpoint; results copied into the dataset files by hand | No |
| Reader-language retrieval parity | `backend/scripts/evaluate_reader_retrieval.py` against a running API | No |
| Embedding-model selection: Recall@10 of at least 0.95 on the instrument's benchmark | Ingestion worker, before an embedding run can be selected (`backend/app/ingestion/embedding.py`) | Enforced at ingestion time, not in CI |
| Deterministic citation identities and provenance of captured answers | `backend/scripts/evaluate_explanations.py` | No |
| Human supported-answer judgments | Offline review page from `backend/scripts/render_explanation_review.py` | No; not yet carried out for the deployed prompt and model |

The offline ranking check fails when a change to the fusion weights,
`RETRIEVAL_RRF_K` or the topic guide lowers its metrics below the committed
floors. It runs on synthetic text built from section headings, so it says
nothing about dense retrieval on the real corpus. No answer-quality metric is
gated in CI: the runtime safeguards in
[`evidence-chat-rollout.md`](evidence-chat-rollout.md) are what stand between a
poor answer and a reader.

## Retrieval

The unit of measurement is the section: a case hits at *k* if one of its
expected sections appears among the first *k* distinct sections returned.

### Constitution, plain-language questions

Two English sets written for the 1999 Constitution (LFN 2004 source edition):

- **Development set**, `plain-language-retrieval-benchmark-v1.json`, 57
  everyday and Pidgin-style questions. The topic guide (`backend/app/legal/topics.py`)
  was built and tuned against these questions.
- **Held-out set**, `plain-language-retrieval-heldout-v1.json`, 40 questions
  (everyday phrasing and the Constitution's own terms). The file says not to add
  topic-guide phrases from it.

Recorded results (bge-m3 embeddings, RRF k = 60):

| Set | Configuration | Fused hit@1 | Fused hit@5 | Source key |
| --- | --- | ---: | ---: | --- |
| Development (57) | Before the topic guide | 0.82 | 0.89 | `baseline_2026_10_12.before_topic_guide` |
| Development (57) | After the topic guide | 0.98 | 1.00 | `baseline_2026_10_12.after_topic_guide` |
| Development (57) | Latest recorded configuration | 0.98 | 1.00 | `results_2026_10_17.fallback_keeps_curated_order.fused` |
| Held-out (40) | Topic guide before section-title scoring, lexical weight 0.15 | 0.82 | 0.95 | `results_2026_10_17.lexical_weight_0_15.fused` |
| Held-out (40) | Latest recorded configuration | 0.95 | 1.00 | `results_2026_10_17.fallback_keeps_curated_order.fused` |

Per-signal results on the held-out set in the same run: dense alone 0.80 hit@1,
lexical alone 0.30, topic guide alone 0.75 before and 0.90 after section-title
scoring (`results_2026_10_17`). The lexical-plus-topic fallback used when query
embeddings are unavailable scores 0.90 hit@1 on the held-out set in the latest
recorded configuration. "Latest recorded configuration" is the last one in each
file (`fallback_keeps_curated_order`); the files do not record a commit, so
whether it matches today's code exactly is not established by the files alone.

How to read these:

- The often-quoted "82% to 98% top-1" is the development set, before and after
  the topic guide. It shows the guide fits the questions it was written for.
- On the held-out set the fused ranking moved from 0.82 to 0.95 hit@1 when
  section titles were added to topic scoring. Both results were recorded in the
  held-out file on the same day, so the held-out numbers were visible when the
  change was adopted. Treat 0.95 as an optimistic estimate.

### Other retrieval sets

- **Per-law benchmarks**, `<law>-retrieval-benchmark.json`: 19 files, 578
  queries in total, one expected provision per query. They are loaded into the
  database with `backend/scripts/load_retrieval_benchmark.py` and used for the
  Recall@10 gate on embedding runs during ingestion. Results are stored on each
  embedding run in the database, not in the repository.
- **Statute routing cases**, `statute-retrieval-benchmark-v1.json` and
  `statute-retrieval-heldout-v1.json`: 7 provisional cases each, derived from
  section-title catalogues and marked `needs_review`. CI asserts that every case
  routes through the topic guide, which means a held-out miss can only be fixed
  by editing the guide; in practice this set is part of the tuning data.
- **Source edition benchmark**, `constitution-source-edition-benchmark.json`: 50
  independently written queries with expected sections, passed to
  `backend/scripts/review_constitution_source_edition.py --benchmark`.
- **Reader-language sets**: Pidgin, Yorùbá, Hausa and Igbo translations of the
  development set (67 cases each: the 57 translated plus 10 native citation
  phrasings) and of the held-out set (40 each). All are `review_status: draft`,
  written without a native-speaker reviewer. No results are recorded in the
  files; [`reader-language-review-checklist.md`](reader-language-review-checklist.md)
  records that a full run in late October 2026 did not show parity with English
  for Yorùbá, Hausa or Igbo.

## Answers

### The 200-case explanation set

`constitution-explanation-evaluation-v1.json` holds 203 English cases pinned to
release `draft-c8d50d87fae9`: 53 topic, 50 exact reference, 29 unanswerable, 25
scenario, 25 follow-up, 10 list, 10 range and 1 missing-instrument case. Every
case is `pending_human_review`. The file's gates are perfect deterministic
citation and provenance checks, zero critical legal-status errors and at least
95% supported-answer judgments. `evaluate_explanations.py` requires at least 200
cases and exits with status 2 until captures and a complete judgment file are
supplied.

The last full live run used prompt `constitution-english-v4` on 9 October 2026
(200 cases, 225 turns): 145 completed explanations, 57 validation failures and
23 insufficient-evidence responses. At least one turn was withheld in 48 of the
170 answerable cases, so at most 152 of 200 could be judged supported. The 95%
gate was not met, and no human judgments were recorded
([`evidence-chat-rollout.md`](evidence-chat-rollout.md)).

The deployed prompt is `constitution-english-v11` (`backend/app/chat/__init__.py`)
on `deepseek-flash` (`render.yaml`). It has not been through the 200-case run or
human review.

## Known weaknesses of the method

- **Tuning on the development set.** The topic guide is hand-written against the
  development questions, so development-set scores overstate performance on new
  phrasing.
- **Small held-out sets.** 40 questions per held-out set: one case is 2.5
  percentage points, and the sets have been looked at during later changes.
- **Statute held-out split was once a pass-all test.** Until November 2026 CI
  required every statute held-out case to hit, which invited fixing misses by
  editing the topic guide. It is now held to a floor, but the seven cases have
  been seen during development.
- **Dense results recorded by hand.** `retrieval_benchmark.py` needs the live
  query embedding endpoint, and its output is pasted into the dataset files;
  only the offline ranking check is recomputed on a change.
- **No human grounding review** of the deployed prompt and model.
- **Unreviewed translations.** Reader-language datasets and glossaries are
  drafts.
- **Edition, not currency.** Ground truth is the stored source edition. A system
  that is accurate against it can still be out of date against current law.
