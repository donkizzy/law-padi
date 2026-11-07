# Deployment plan: twenty laws to production (7 November 2026)

Status: deployed on 7 November 2026. Commit `d5d7f58` is live on Render and Cloudflare, and `composite-2026-11-06-twenty-laws` is the production release on Neon (316 MB). Pre-release Neon dump: `backend/storage/statute-review/tier1-2026-11-05/neon-before-twenty-laws.dump`. Rollback release: `draft-c8d50d87fae9`.

Production search runs in lexical mode, because `EMBEDDING_QUERY_ENABLED` is off. The Recall@10 figures in this plan measure vector search, so they do not describe what readers get today.

## Where things stand

| Item | Now |
|---|---|
| Local release | `composite-2026-11-06-twenty-laws`, 15,790 entries, 16,181 provisions, Recall@10 0.957, gates empty |
| Neon | Release `draft-c8d50d87fae9`, Constitution only, 47 MB, schema `c9d0e1f2a3b4`, 1 admin, 7 guest conversations from 16 to 27 October, 1,228 AI spend reservations |
| Code | `origin/master` is `7438ee6`. Local `master` is 3 ahead. Uncommitted: the source-read fix, storage changes and NRS/JRB work |
| Files | `lawpadi` R2 bucket, the same bucket local and production use. 10,897 references checked, none missing, no checksum mismatch |
| Hosting | A push to `master` deploys at once: Render backend and Cloudflare frontend. No CI gate |

## Decision needed: how to replace the database

**Recommended: copy the release, keep the database (Option A).** A full restore of the local database is the wrong tool for this data, for the reasons below. Option A puts exactly the same laws, vectors and source references live.

| | A: `publish_release.py` | B: full `pg_restore` |
|---|---|---|
| Size on Neon | 346 MB in the rehearsal | 1.44 GB; expected to exceed the Free plan storage limit, so confirm the plan first |
| Accounts | Keeps the Neon admin | Brings 372 local accounts, nearly all test users, and the local admin with its development password |
| AI spend ledger | Kept | Lost. The runbook says not to reset it |
| Review history | Stays local, by design | Copied in: runs, candidates, decisions, idempotency records |
| Checks | Row digests, source hash checks, rehearsal mode, single transaction | None beyond the restore itself |
| Rollback | Activate the previous release | Restore the Neon branch |

If you want Neon wiped first because there are no real users, use **Option C**: restore an empty schema, then run Option A. That clears the admin, the 7 conversations and the spend ledger, so the ledger must be carried over or knowingly reset. It gains little over A.

Option B stays available only if you still want it after the table above. It would need a paid Neon plan or a slimmed dump, removal of the test accounts, and a new admin password.

## Before any production step

These are all local and change nothing live.

1. Finish the code freeze.
   - Commit the source-read fix (`search.py`, `test_legal_search.py`).
   - Decide what happens to the uncommitted NRS and JRB work. It is not needed for this release; leave it out unless its owner signs it off.
   - `r2_blob_store.py` still has uncommitted storage changes. Confirm with their owner whether they ship.
2. Run backend tests, `bun run build`, `bun run lint` and the proxy tests on the frozen commit.
3. Build the production image from a clean checkout of that commit, not this working tree:

   ```bash
   docker build -f deployment/render/Dockerfile -t constitution-ng-api:release .
   ```

4. Check memory. The twenty-law corpus took a process to about 270 MB, which should fit Render Free's 512 MB, but it has not been measured in the Render image under load.
5. Rehearsal: done on 7 November against a copy of Neon. Migrations, copy, activate and the rollback dry run all passed, and the Constitution's 1,850 provisions matched exactly.
6. Confirm the Neon plan's storage limit in the console.

## Release order

The order matters. The new code reads `user.auth_version`, so **the schema must go first**. The old code ignores the new column and table, so migrating early is safe; pushing early is not.

1. **Tell anyone working in this checkout to stop pushing.** The five earlier commits were already pushed by someone, and they are live on Render now.
2. **Create a Neon restore point:** a named branch, for example `pre-twenty-laws`, in the Neon console. Also take a `pg_dump` to private storage.
3. **Migrate Neon to the frozen head,** running locally with the deployment credentials, because Render Free has no pre-deploy shell. This goes from `c9d0e1f2a3b4` to `e3f4a5b6c7d8`. The steps add a column, a table and wider benchmark fields. Confirm with:

   ```bash
   SELECT version_num FROM alembic_version;
   ```

4. **Copy the release, dry run first.** Without `--apply` the transaction rolls back. Run these where `localhost:5432` is the Docker database, because Homebrew Postgres shadows that port on this machine; the rehearsal used a one-off container on the database container's network.

   ```bash
   .venv/bin/python deployment/publish_release.py copy --release-version composite-2026-11-06-twenty-laws
   .venv/bin/python deployment/publish_release.py copy --release-version composite-2026-11-06-twenty-laws --apply
   ```

   Readers keep the old release until the activate step.
5. **Deploy code:** push `master`. Render and Cloudflare build automatically. Wait for both, and confirm the API's revision matches the frozen commit.
6. **Activate the release,** dry run first, the same way:

   ```bash
   .venv/bin/python deployment/publish_release.py activate --release-version composite-2026-11-06-twenty-laws
   .venv/bin/python deployment/publish_release.py activate --release-version composite-2026-11-06-twenty-laws --apply
   ```

Activating after the deploy means the new citation code is live before FREP is served, so Order and Rule citations never appear as "Section II.1".

## Checks after release

- `/healthz`, and the revision matches.
- Sign in as the Neon admin, and sign out.
- `/legal/instruments` lists 20 laws, and `/legal/releases/current` shows the twenty-law release.
- Search: "what does rape mean under the Penal Code" returns s.282, "time limit fundamental rights" returns Order III Rule 1.
- Notices appear on Cybercrimes s.44, Minimum Wage s.3 and Penal Code s.384.
- A source PDF opens through the signed R2 link, for one new law and for the Constitution.
- Direct calls to the Render origin without the proxy credential still return 403.
- Check Render memory, Neon storage and connection use after a sleep and wake cycle.

## Rollback

| Failure | Action |
|---|---|
| Copy fails | Nothing to undo. It runs in one transaction |
| New code fails | Roll back the deploy in Render and Cloudflare. The migrations can stay |
| New release is wrong | Run `activate` with `--release-version draft-c8d50d87fae9` |
| Database is damaged | Restore the `pre-twenty-laws` Neon branch |

## Known limits of this release

- **Penal Code:** a retyped copy with unverified penalties and missing sections. It is marked historical, and 16 flagged prison terms are unread. Consider holding it back if launch quality matters more than coverage.
- **AI chat:** the launch gate in `deployment-status.md` is still open. This plan does not change generation settings. `render.yaml` and `deployment/render.env` both set `CHAT_GENERATION_ENABLED` to true with the kill switch off, while `CHAT_PROVIDER_CAPACITY_APPROVED` is false. Confirm that combination is what you want before release.
- **Non-English notices:** Pidgin, Yoruba, Hausa and Igbo strings are unreviewed drafts.
- **Backups:** R2 holds files only. Laws and vectors live in Postgres, so Neon needs its own backup. `deployment/render/backup-workflow.yml` exists, but it is not in `.github/workflows`, so nightly backups do not appear to be running.

## Local state

The local database is on `e3f4a5b6c7d8`, and the local backend runs a clean build of `10be838` plus the source-read fix. The same rule applies to production: migrate Neon before pushing.
