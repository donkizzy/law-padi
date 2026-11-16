# Multilingual evaluation plan

How Nigerian Pidgin (`pcm`), Yorùbá (`yo`), Hausa (`ha`) and Igbo (`ig`) are measured before each one is switched on. The design is "English core, translated edges": the question is translated to English, the existing English retrieval and answer checks run unchanged, and the verified English answer is translated back.

**Status.** `render.yaml` enables all five reader languages in production, with
non-English answers labelled Beta. The enable gates below have not been shown
to pass for any non-English language: no translation evaluation set exists yet,
and the late-October retrieval run did not show parity for Yorùbá, Hausa or Igbo
([`reader-language-review-checklist.md`](reader-language-review-checklist.md)).
The launch exception in
[`evidence-chat-rollout.md`](evidence-chat-rollout.md#launch-exception-recorded-16-november-2026)
records that generation is enabled with all five languages; it does not record
these language gates as met.

All data below is `review_status: "draft"`. It was drafted and cross-checked without a native-speaker reviewer, so it must never be described as reviewed.

## Data files

| File | What it holds |
|---|---|
| `backend/app/languages/data/glossary-{lang}.json` | 166 legal terms per language, including the fixed answer heading "What you can do:". Each term has `en`, `target`, `alternatives`, `note`, `confidence`, and `locked` on terms that must stay in English form. |
| `eval/datasets/plain-language-retrieval-benchmark-{lang}-v1.json` | The 57 English benchmark cases translated (same order and `expected_sections`; `source_query` holds the English text), plus 10 native citation phrasings with `kind: "citation"`. 67 cases in total. |
| `eval/datasets/plain-language-retrieval-heldout-{lang}-v1.json` | The 40 English held-out cases translated (same order, `kind` and `expected_sections`). Never tune the topic guide on these. |

### How the glossaries were built

Each glossary comes from two independent drafts made with different models from the same English term list. The drafts were compared after folding (no tone marks, hooks or apostrophes):

- **Agree:** the note says "Two drafts agree."
- **Overlap or minor wording difference:** the note gives the second draft's form, which is also kept under `alternatives`.
- **Disagree:** the note says "Needs native review" and confidence is capped at `medium`.
- **Judgement calls** made while reconciling are written into the note. For example, Hausa uses the gender-neutral "za ku" in the answer heading, and the Yorùbá entry for "sex" warns against "ìbálòpọ̀".

**Locked terms** keep their English form in answers so that citations can still be checked: Constitution, section, subsection, paragraph, chapter, schedule, Act, Administration of Criminal Justice Act and Police Act. Their local forms (for example abala, sashe, nkeji) are listed only so the system can recognise questions that use them.

### Low-confidence terms (need a native reviewer first)

- **pcm:** none. Note that 34 terms are `medium`, mostly wording choices.
- **yo:**
  - remand
  - naturalisation
  - recall (of a legislator)
  - immunity
  - secular
- **ha:**
  - naturalisation
  - secular
- **ig:**
  - remand
  - naturalisation
  - section (the native word is unsettled between nkeji, akụkụ and nkebi)
  - schedule
  - federation
  - recall
  - immunity
  - qualification
  - secular

## Enable gates (per language)

A language is switched on in `CHAT_LANGUAGES_ENABLED` only when **all** of these hold for it:

1. **Retrieval:** hit@5 on that language's benchmark and held-out sets is at least the English hit@5 minus 5 points.
   - Compare against English measured on the same release, embedding profile and settings, in the same run.
   - Gate each set separately: benchmark against English benchmark, held-out against English held-out.
2. **Deterministic translation checks:** at least 98% of the translation eval set (about 60 verified English answers per language) passes. The checks are:
   - same block count
   - `evidence_ids` untouched
   - every section reference and number preserved
   - locked terms in English form
   - no quotation marks
   - length ratio within bounds
   - the detector agrees on the target language
3. **No dropped conditions:** the cross-model judge, reading a back-translation, finds zero dropped or changed legal conditions on the judged set. These are the qualifiers like "unless", "within a reasonable time" and "except", plus exceptions and time limits.
4. **"Beta" label:** a language passing gates 1 to 3 can launch only as **Beta**, with an "English version" toggle. Removing "Beta" needs a native-speaker reviewer to sign off on:
   - the glossary, starting with every `low` and "Needs native review" term
   - a sample of translated answers

   Once that is done, set `review_status` to `"reviewed"` with the reviewer and date.

Pidgin is the pilot. Yorùbá, Hausa and Igbo go on one at a time as each passes its own gate.

## How `backend/scripts/retrieval_benchmark.py` will consume these files

The script already reads `cases[].query` and `cases[].expected_sections` and ignores other keys, so the new files load unchanged. The planned changes:

1. **Translated mode (the gating number).** When a dataset's `language` is not `en`:
   - Run each query through the production question-translation step [1] (`{language, english_question}`).
   - Retrieve with `english_question` exactly as production `prepare_run` does: the citation parse runs on both the original and the English text, so digits survive.
   - Cache translations to a JSON file keyed by `(prompt_version, provider, query)`, so reruns are reproducible and don't spend budget.
   - Report the translation provider and prompt version next to the metrics.
2. **Raw mode (diagnostic).** Also retrieve on the untranslated query, using the folded keyword path and topic guide. This shows how much depends on translation and whether the token fold works. It is not a gate.
3. **Oracle mode (ceiling).** Retrieve on `source_query`, which reproduces the English result. The gap between oracle and translated is the loss from translation alone.
4. **Breakdown by `kind`.** Report `everyday`, `keyword` and `citation` separately.
   - Citation cases test whether the local words for "section" and spelled-out numbers resolve to the right section. Examples: "abala kẹtàdínlógójì", "sashe na talatin da shida", "nkeji iri atọ na asaa".
   - A citation miss is a translation or parser bug, not a ranking problem.
5. **Output.** Pass several datasets in one run, English first, so the gate check can compute `lang hit@5 ≥ en hit@5 − 0.05` itself and print PASS/FAIL per language.

Example once translated mode exists:

```bash
cd backend && uv run python scripts/retrieval_benchmark.py ../eval/datasets/plain-language-retrieval-benchmark-v1.json ../eval/datasets/plain-language-retrieval-benchmark-yo-v1.json ../eval/datasets/plain-language-retrieval-heldout-v1.json ../eval/datasets/plain-language-retrieval-heldout-yo-v1.json
```

## Known gaps

- **Spelling variants.** Hausa uses Nigerian `'y` spelling; the `ƴ` form folds to the same match form. Igbo `nwaanyị`/`nwanyị` and Yorùbá loanword spellings (Kọmíṣọ́nà/Kọmísánà) vary. Alternatives cover the common ones.
- **Keyword cases.** Pidgin speakers type legal titles in English, so the Pidgin keyword cases stay close to English. The Yorùbá, Hausa and Igbo keyword cases mix in English names where the local press does (Grand Kadi, federal character, Code of Conduct Tribunal).
- **Translation eval set.** The ~60 answers per language for gates 2 and 3 are not built yet.

## Release-gate tooling (27 October 2026)

`backend/scripts/evaluate_reader_retrieval.py` now evaluates all 525 existing
English/native benchmark and held-out queries through the actual search API,
pinned to one published release. It records per-split English comparisons and
returns a failure status when retrieval parity is not demonstrated. This replaces
the earlier future-tense translated-mode instructions for release-gate runs;
`retrieval_benchmark.py` remains useful for individual ranking-signal diagnostics.

Answer translation now uses `answer-translation-v2` / `translation-judge-v2`.
The judge covers blocks, missing-fact prompts and follow-ups; rejected output can
be repaired once, within the same spend/deadline controls. The English fallback
and every deterministic safeguard remain. Existing v1 captures do not validate
v2. See [the native review checklist](reader-language-review-checklist.md) for the
uncompleted human and ≥60-answer-per-language gates. No language is marked
native-reviewed by these code changes.
