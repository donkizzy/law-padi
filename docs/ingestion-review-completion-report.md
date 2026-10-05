# Constitution review and ingestion completed — 5 October 2026

Local development run `c8d50d87-fae9-4538-af68-d6de4de1ce77` is
`ready_to_publish`. Review, materialization, embedding and indexing are complete.
Release approval and publication remain with the user. The draft release
`draft-c8d50d87fae9` remains `building`, with no approval actor or timestamp,
no active retrieval target and no production release. The application's
**Validate** action can change release approval status; it was deliberately
not invoked. Index validation was performed independently without approval.

## Verified outcome

| Check | Result |
| --- | --- |
| Candidates reviewed and materialized | 1,851 |
| Approval decision records | 1,851 |
| Findings resolved with individual evidence | 144 |
| Open findings / operational alerts | 0 / 0 |
| Candidate text revisions | 0 |
| Historical text versions | 1,811 |
| Materialized text exactly matching trimmed reviewed candidate text | 1,811 |
| Ready pgvector segments / embeddings | 1,829 / 1,829 |
| Vector dimensions | 1,024 |
| Independent revalidation of index counts, dimensions and canonical joins | Passed |
| Retrieval benchmark | Recall@10 0.98; nDCG@10 0.977246; 50 queries |
| Required Recall@10 gate | 0.95, unchanged |
| Dense and hybrid retrieval smoke tests | Passed for right to life, freedom of expression and Judicial Oath |
| Unfinished ingestion tasks / candidates beyond Constitution boundary | 0 / 0 |
| Release validation gates remaining | None |
| Release approval / publication | Pending user decision |

The original 235-page PDF remains unchanged. Its SHA-256 is
`26c1b7f15fb6eae02aa2064e5cc2c3fa5d84f6c7c0b04a0f4e94a8183df3e838`.
The source manifest hash is
`1e12791867fd8d8b10542b3c431c0b90c1c79a6e17cbbc10cdadecba579fe56f`.
The ready index build is `3333d1fb-0437-420a-82a6-8bc3bb261b10`.
Full outcome evidence, hashes and canonical smoke-test results are retained in
[the completion evidence](ingestion-review-completion-evidence-2026-10-05.json).

## Review decisions and source scope

The source-specific review reproduced all candidate structure, text and original
PDF coordinates before approval. The 136 short-text confidence findings were
resolved after those checks. Seven punctuation findings and one numbering gap
were resolved as source-preserving exceptions under the user's explicit policy.
Each finding retains its individual reason, evidence and reviewer audit record.
This establishes faithful preservation of the uploaded edition; it does not
establish independently adjudicated legal accuracy or current consolidated law.

Both printed Section 189 identities remain:

- `constitution-1999.chapter6.part1.section189`, PDF page 80, following Section 167.
- `constitution-1999.chapter6.part2.section189`, PDF page 88.

There is no canonical Section 168. No corrected identity was invented.
Source punctuation remains as printed on PDF pages 44, 87, 124 and 138, including
the duplicated findings on parent sections and their subsections. Other source
wording anomalies were preserved. The Constitution ends after the Judicial Oath
on page 172; appended instruments remain in the original PDF for later separate
ingestion and contributed no candidates to this release.

## Workflow changes and validation

The admin queue now displays the actual filtered total, paginates beyond 100
items, and defaults to the selected run's outstanding review candidates.
Historical materialization creates historical versions without reusing current
law versions; the release includes this edition's materialized versions.
Source-edition metadata and accepted exceptions remain visible during release
review and survive the later validation action.

The incorrect Hugging Face sentence-similarity URL was replaced by a profile
override for feature extraction, shared by corpus and query embeddings.
No credentials or dependency lockfiles were changed for this work.

The first embedding attempt failed before producing a benchmark score. Its
immediate retry erased the original provider exception, preventing precise
diagnosis; a request timeout is consistent with the observed 60-second gap.
The worker was stopped before further retries, and durable batch checkpoints,
input/configuration cache guards, hash checks, progress recording, a longer
request timeout and explicit provider failure reporting were added. A regression
test confirms retries reuse completed batches and re-embed changed inputs.
The same run then completed successfully with retained checkpoints.

Validation passed: 117 backend tests in disposable databases, 13 admin browser
tests, backend mypy/ty/Ruff checks, frontend Biome checks, frontend production
build and Git whitespace checks. The local admin URL responds successfully at
<http://localhost:8000/admin>. Tests did not run against the live corpus database.

## Limitations for release review

The benchmark retained one strict parent-level miss: query `q001` expected
Section 1, while the relevant Section 1(3) ranked fourth. The expected labels,
queries and threshold were not changed to improve the score.

The recorded BAAI/bge-m3 model revision is
`5617a9f61b028005a4858fdac845db406aefb181`, but the Hugging Face serverless
endpoint does not confirm revision pinning. `provider_revision_pinned=false`
is retained in the profile and source-edition evidence. Actual vectors and
checksums are retained; reproducibility against a provider-pinned deployment
remains a release consideration.

The [recovery plan](ingestion-review-recovery-plan.md),
[baseline inventory](ingestion-review-audit-2026-10-05.json),
[unchanged benchmark](constitution-source-edition-benchmark.json), and
[source-specific review script](../backend/scripts/review_constitution_source_edition.py)
provide the audit trail and approach used to complete this run.

## Publication workflow follow-up

The user's initial Publish request used release version 4 while the draft was
still `building`. A ready ingestion run does not approve its release: the
separate **Validate** action checks the publication gates and moves a clean
draft to `approved`. The frontend now disables Publish until that status is
reached and explains the required step. Its regression test confirms the
subsequent Publish request uses refreshed version 5.

The local development account also uploaded the source. Existing actor
separation requires a different publisher or a superuser-supplied override
reason. The UI now displays that requirement and waits for a reason when the
current superuser is the uploader. No override reason was invented or applied
to the live release. The rebuilt UI passed all 14 admin browser tests and build
checks; release approval and publication remain user actions.
