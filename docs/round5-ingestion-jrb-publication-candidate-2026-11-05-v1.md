# JRB local publication candidate

5 November 2026, Africa/Lagos. The JRB-only draft and composite passed the local data and index gates. This record binds the proposed release. Publication requires a separate decision after the implementation blockers below are resolved.

| Field | Value |
| --- | --- |
| Composite release | `composite-2026-11-05-jrb-v1`, `fe534f78-1823-4f2c-bd57-2e8302372ec1`, lock 5 |
| Composite manifest SHA-256 | `191f2d2c802ec954c5a7b3f846e9d16bf4d6594a389d309987e8635a5b43a294` |
| Composite build and embedding run | `b84fad0d-c298-468e-a92f-5e50321a1e45`, `13a747d1-254e-4fd6-9c9a-9bd836ea1b66` |
| Composite build checksum | `98fd8305d3965807a2c7b19e690b5f91d9061dca045fb752822a56eeba016409` |
| Existing enacted target | Release `5f3fe60c-c691-4ced-a60b-05aae29697c6`, release lock 6, target lock 4 |
| Base manifest SHA-256 | `b7ad4d1ead3683de6f4b8562310f0ca66f2e8815a2c42ae36da4987b315e45d0` |
| Existing enacted build and embedding run | `63b7b94c-9e83-4fd2-b108-147fd2d8ea57`, `538d2909-7b48-433e-a6e9-5d5575b81ca5` |
| Added member | JRB draft `5c967020-e85f-498b-960b-f2b5f536f787`, lock 5, 335 as-enacted text entries |
| Carried content | All 11,212 entries from the active release, with the same version, source and original ingestion provenance |
| Candidate entries and vectors | 11,547 entries and 12,398 vectors |

[Private JRB index](round5-ingestion-jrb-embedding-2026-11-05-v1.md) · [Composite stage log](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-embedding-v1/composite-progress-v1.jsonl) · [Index verification](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-embedding-v1/composite-index-progress-v1.jsonl) · [Read-only checks](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-embedding-v1/composite-validation-v2.json)

## Verified results

The composite reuses 12,062 base vectors and 336 JRB vectors. The readback joined each vector to its exact provision version, source, segment ordinal, retrieval-text hash, authoritative-text hash and vector hash. There were zero missing or extra rows. The profile is the same 1,024-dimensional BAAI/bge-m3 profile as the existing target. The composite hit 367 of 370 benchmark questions in the top ten, including all 28 JRB questions. Overall Recall@10 was 0.991892 and nDCG@10 was 0.910967.

Eleven sample JRB queries found the expected provision or its approved answer text within ten results in each of dense, lexical and hybrid retrieval. Hybrid ranking returned the exact provision or a descendant for five queries and the authoritative containing provision for six. Lexical ranking returned an exact provision or descendant for ten and an authoritative containing provision for one. The JRB-scoped hybrid checks returned canonical historical evidence from the JRB source. The prior exact canonical lookups checked both naira amounts and all three schedule endings. The aggregate conversation release pins matched the pre-composition snapshot. [Exact canonical lookups](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-apply-v1/private-lookups-v2.json)

Hugging Face returned 47 checkpointed batches. JRB used 21 document batches and two benchmark batches. The composite used 24 benchmark batches. Checkpoint telemetry recorded one attempt per batch. Provider billing data was unavailable. The composite's reported zero document embedding cost reflects vector reuse and does not establish the query charges. Both pre-write local database archives decoded in full. The pre-composite backup is 387,773,594 bytes, SHA-256 `3354200b0a681b6f6dcc508cbc16b6cab350ab3cac20ec41a16edcec2a1f19c5`. Restore was not tested. [Backup evidence](../backend/storage/statute-review/ingestion-round5-2026-11-05-jrb-embedding-v1/composite-backup-validation-v1.json)

## Publication blockers and proposed target change

The deployed promotion service updates publishing metadata and emits a new event for every contributing ingestion run. The active base contributes nine existing runs. Promotion through that service would therefore modify carried runs, which conflicts with the user's protection requirement. A focused promotion fix would exclude runs already present in the previous production release from those updates and keep updates for newly added runs and the composite run. A regression should verify carried run and publishing-step versions and events, while checking that the new runs and target transition are recorded atomically. This is outside the previously authorised two code fixes. [Promotion implementation](../backend/app/ingestion/service.py#L3691)

The deployed citation parser still maps the full-title JRB section 41 citation to the Constitution. The already approved workspace citation and reader fixes passed focused tests. They need to be loaded into the local runtime and rechecked before promotion. The draft is intentionally inaccessible through the published reader routes until promotion. Public Browse, citation lookup and source presentation are post-promotion checks. [Citation and reader implementation](round5-ingestion-jrb-implementation-2026-11-05-v1.md)

A later approved publication would move the enacted target at lock 4 to the exact composite release, build and embedding run above, at expected release lock 5. The existing operator was also a source uploader, so publishing with that account requires a separate explicit actor-separation override with an audited reason, or a distinct authorised publisher. The existing release, build and embedding run in the table are the rollback target. The pgvector promotion transaction rolls back automatically if it fails before commit. After commit, the supported public promotion entry point requires an approved release and ready build, so a rollback procedure must account for the retained release's retired status and promoted build before the switch is authorised. The archive is recovery evidence. [Promotion and rollback runbook](ingestion-runbooks.md)

No publication action was issued. The current active pointer is still the base at lock 4. The next step is separate permission for the focused promotion fix and verification of the local runtime, followed by a publication decision for the exact composite.
