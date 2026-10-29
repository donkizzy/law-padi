# Reader-language release review

This checklist is the remaining human approval work for QA-005. Automated checks
and the Beta label do not approve a language. Do not change a draft's review
status or fill reviewer names until that person has completed the review.

## Reproducible automated evidence

From `backend/`, run `uv run python scripts/evaluate_reader_retrieval.py` against
the intended local API (or pass `--base-url`). It evaluates every existing
benchmark and held-out case through production question understanding and search,
with two clients, on one pinned published release. The JSON records the release,
understanding prompt, source hashes, per-split metrics and failed queries. A
nonzero exit means at least one language has not demonstrated retrieval parity.
Do not tune to individual held-out misses; make independently justified changes
and use a new held-out set if it becomes development data.

The required retrieval gate is per-language **hit@5 no more than five percentage
points below English**, separately on benchmark and held-out sets. Every request
must complete on that release. Never substitute the smaller production QA sample
for this gate.

## Native review and answer translation

The 27–28 October full live retrieval run failed parity for Yorùbá, Hausa and
Igbo (see QA-025 in `production-qa-2026-10-27.md`). Before approving release,
native reviewers must also adjudicate original question / English rendering
pairs, including offices, actions, negation and uncertain section numbers.
The answer-translation judge does not validate input-question understanding.
Evaluate any resulting understanding changes on a fresh held-out set; retain
failed captures and do not replace them with hand-written expected translations.

For each language, a fluent reviewer needs to examine:

1. Its `backend/app/languages/data/glossary-<language>.json`, starting with low
   confidence terms and every `Needs native review` entry.
2. All nine interface namespaces in `frontend/src/locales/<language>/`.
3. A versioned set of at least 60 verified English answers and their translated
   outputs, including rights, exceptions, time limits, application/jurisdiction,
   missing-fact prompts and follow-up questions. Use the current translation and
   judge prompts; a previous prompt's approval does not approve a new one.
4. The deterministic validation report (at least 98% passing), with zero changed
   legal conditions in independent semantic judgments. Include fallback and
   provider-failure counts; do not silently drop failed outputs from the sample.

Record the release, provider/model, understanding/translation/judge/glossary
versions, captured-answer digest, reviewer, date and covered cases/namespaces.
Keep the original English evidence and answer available beside each translation.

| Language | Glossary | Interface | ≥60 answer evaluation | Reviewer / date | Status |
| --- | --- | --- | --- | --- | --- |
| Pidgin (`pcm`) | Draft | Draft | Pending | — | Not approved |
| Yorùbá (`yo`) | Draft | Draft | Pending | — | Not approved |
| Hausa (`ha`) | Draft | Draft | Pending | — | Not approved |
| Igbo (`ig`) | Draft | Draft | Pending | — | Not approved |

Current repair behavior remains conservative: at most two translation attempts,
all displayed items checked, target-language/meaning/condition judgment for the
judged languages, budgeted calls, and a bounded translation deadline. Rejected
translations keep the verified English answer. These safeguards reduce exposure;
they do not constitute native review or unconditional language-release approval.

Only after review should the actual glossary metadata, catalogue README, this
checklist and the QA tracker be updated together. No native reviews were performed
by the automated fix pass.
