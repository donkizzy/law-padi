# Prompts for the remaining work

Status on 19 November 2026:

| Prompt | Status |
| --- | --- |
| 1. Railway cutover | Done on 18 November; see `RAILWAY-CUTOVER-2026-11-18.md` in the audit folder. |
| 2. Post-cutover cleanup | Done on local branch `chore/remove-render`, not pushed. |
| 3. GitHub hygiene | Ruleset and labels are already applied. The Support request is drafted in `GITHUB-SUPPORT-REQUEST.md` in the audit folder. |
| 4. Local `.env` | Done: `DATABASE_URL` was rebuilt from `POSTGRES_PASSWORD`, and migrations apply to head. |

Each prompt stands alone. Paste one per new chat, opened in `/Users/amosgodwin/WebstormProjects/law-padi`. Run them in this order: 1, then 2 once cutover is confirmed stable. 3 and 4 can run any time.

Before prompt 1, do the Cloudflare step by hand in the dashboard (Worker → Settings → Variables and Secrets):

- Add `API_ORIGIN` and `PUBLIC_SITE_URL` as **build** variables, with the same values as the runtime ones.
- Add `BUN_VERSION=1.3.12` as a build variable.
- Keep `ORIGIN_PROXY_SECRET` unchanged.

---

## Shared rules (already included in every prompt below)

- Never open or print `.env`, `deployment/*.env`, `deployment/project.json` or any secret value. Pass secrets by file or environment variable, never in chat.
- Commits: author "Amos Godwin <amosgodwin500@gmail.com>", `--no-gpg-sign`. No AI co-author trailers, no "Generated with" lines, no session links.
- Never send my email address to external services.
- Commit or push only when I say so. Never force-push.
- Ask before any irreversible or outward-facing step: DNS, deleting a database or service, a write freeze, a production migration.

---

## 1. Railway cutover

```
Context: constitution.ng (repo donkizzy/law-padi, branch master at ec15e95, all 7 CI workflows green). It is a FastAPI + Postgres/pgvector API, a separate ingestion worker and a chat worker, with a React frontend served by a Cloudflare Worker (assets + /api proxy) and R2.

Today the API runs on Render (auto-deploy is OFF, it stays as the fallback) against Neon Postgres. I have Railway Pro. The decided target is API + workers + Postgres (pgvector) on Railway, region EU West (Amsterdam). Neon was rejected for cost. Cloudflare Worker and R2 stay where they are.

Everything is prepared in the repo. Read these first, in order:
- docs/runbooks/railway-migration.md (the procedure, which you will follow step by step)
- docs/adr/0007-* (the Railway decision)
- deployment/railway/README.md, railway.ts (config as code; apply with `railway config plan` and then `railway config apply`; railway.json/railway.toml are not used), run.sh, postgres/, verify.sql
- docs/runbooks/observability.md (/livez, /readyz, heartbeats, Sentry)
- deployment/cloudflare/README.md (API_ORIGIN, ORIGIN_PROXY_SECRET, PUBLIC_SITE_URL)

Pending migrations will run on the first Railway deploy, and two of them can abort on purpose:
- a3c3553158d1 adds a case-insensitive unique email index. It aborts if two accounts' emails differ only by case, and reports a count.
- d8e9f0a1b2c3 drops the remote-vector storage. It aborts if vector_index or the release_promotion_attempt collection columns hold history, unless ALLOW_DROP_VECTOR_HISTORY=1 is set.
So BEFORE the write freeze, run the runbook's two read-only checks against Neon. Tell me the counts. If either is non-zero, stop and propose a fix (merge accounts, or export the history then set the flag) for me to approve.

What I want from you:
1. Walk the runbook. Do each step you can do with the Railway CLI or SDK, psql or curl. For each one, tell me what you are about to run and what you expect.
2. Pause and ask me before: the write freeze, the pg_dump/restore into Railway, the first production migration, and switching Cloudflare API_ORIGIN to https://<api-service>.up.railway.app.
3. After the switch, verify:
   - /livez and /readyz on Railway directly and through the Worker;
   - a sign-in;
   - a chat answer with citations;
   - worker heartbeats;
   - the row counts from verify.sql against the Neon numbers.
4. Give me the rollback in one paragraph: point API_ORIGIN back at the Render URL and resume Render against Neon.
5. Write a short cutover log into ~/Documents/constitution-ng-audit-2026-11-16/RAILWAY-CUTOVER-<date>.md. Include times, commands without secrets, check results and anything that differed from the runbook. Propose runbook edits for anything wrong, but don't commit them until I say.

Rules:
- Never open or print .env, deployment/*.env, deployment/project.json or any secret. Pass secrets by file or env var.
- Never send my email address to external services.
- Commits are authored "Amos Godwin <amosgodwin500@gmail.com>" with --no-gpg-sign and have no AI co-author trailers or "Generated with" lines.
- Commit or push only when I say so. Never force-push.
- Ask before anything irreversible or outward-facing.
```

---

## 2. Post-cutover cleanup (run only once Railway has been stable for a few days)

```
Context: constitution.ng (repo donkizzy/law-padi, master). Production has moved from Render + Neon to Railway (API, workers, Postgres in EU West). The Cloudflare Worker now proxies to the Railway API. Render and Neon are no longer needed as a fallback. First confirm that with me: ask whether Railway has been stable and whether I've exported anything I want from Neon.

Task: remove Render from the codebase and tidy the leftovers, in focused commits on a new branch off master (e.g. chore/remove-render).

1. Delete the Render deployment:
   - deployment/render/
   - docs/runbooks/render.md
   - .github/workflows/render-ci.yml
   - Render-only scripts, tests and fixtures. Grep for "render", "onrender" and "RENDER_" in deployment/, scripts/, backend/, .github/ and docs/.
   - Update every reference: README, docs/README, docs/architecture.md, ADRs (add a "superseded by 0007" note; never delete an ADR), docs/runbooks/*, deployment/README.md and AGENTS.md if it is mentioned there.
2. In the Cloudflare Worker (deployment/cloudflare/worker.ts and its tests), remove the allowance for *.onrender.com origins so only the configured Railway origin is accepted. Add or adjust a test that proves an onrender.com origin is now rejected.
3. Find the "repository access required" wording for corrections. It is in frontend/src/locales/en/pages.json, and frontend/tests/legal-home.spec.ts plus deployment/cloudflare/__snapshots__/seo-output.test.ts.snap reflect it. Replace it with wording that tells a visitor how to report a correction without needing GitHub access. Show me two or three options first. The copy must answer plainly and never mention "AI". Then update the spec and regenerate the snapshot.
4. Optional, so ask me first: PUB-16 Worker rename, per the steps in deployment/cloudflare/README.md.
5. Verify locally:
   - cd backend && uv run bash scripts/lint.sh && uv run bash scripts/test.sh (87% branch coverage floor);
   - bun run lint, bun run typecheck, bun run build, bun run test:mocked;
   - the Cloudflare Worker tests;
   - the Railway CI checks (see .github/workflows/railway-ci.yml).
   Report the results honestly, including any failures with their output.
6. Show me the diff summary and commit list. Push and open a PR only when I say so.

Rules:
- Never open or print .env, deployment/*.env, deployment/project.json or secrets.
- Commits are authored "Amos Godwin <amosgodwin500@gmail.com>" with --no-gpg-sign. No AI co-author trailers, no "Generated with" lines, no session links.
- Short, imperative, scoped commit subjects (e.g. "deploy: remove the Render service").
- Don't touch frontend/src/client/ or routeTree.gen.ts by hand.
- Commit or push only when I say so. Never force-push.
```

---

## 3. GitHub hygiene: branch protection, labels and the old-commit purge

```
Context: repo donkizzy/law-padi is public. Its history was rewritten and force-pushed on 2026-11-17/18 (master at ec15e95; every commit by "Amos Godwin <amosgodwin500@gmail.com>"; no konga.com address; no AI trailers). Old commits are still reachable on GitHub through pull requests #1 and #2. Backups of the old history are in ~/Documents/constitution-ng-audit-2026-11-16/*.bundle.

Tasks:
1. Read docs/runbooks/branch-protection.md. Apply it with the gh CLI (gh api): branch protection or a ruleset on master, and the labels it lists. Before running, show me the exact gh commands and the required status-check names. The names must match the current workflow job names in .github/workflows/; check them against a recent successful run with `gh run list` / `gh run view`, and drop render-ci if Render has already been removed. After applying, read the settings back and confirm they match.
2. Draft a GitHub Support request for me to send myself; don't send anything. It should ask them to run garbage collection on donkizzy/law-padi and to remove cached views of the commits referenced by PRs #1 and #2, after a history rewrite to remove personal data. Include the PR URLs and say the force-push is done. List a handful of old commit SHAs if you can find them with `gh api repos/donkizzy/law-padi/pulls/1/commits` (and the same for /2). Don't put my email address in the draft.
3. Check that Dependabot is enabled and that the workflows run with least-privilege permissions; Zizmor should already enforce this. Only report; change nothing unless I approve.

Rules:
- Never print tokens or secrets.
- Ask before any settings change goes live.
- No commits are needed. If one turns out to be needed: author "Amos Godwin <amosgodwin500@gmail.com>", --no-gpg-sign, no AI trailers, and commit/push only when I say.
```

---

## 4. Local .env database password

```
In /Users/amosgodwin/WebstormProjects/law-padi, the backend's local DATABASE_URL in the ignored .env has a stale password, and local Postgres (docker compose service "db") rejects it.

Fix it without printing or reading secret values into the chat:
- Compare only the key names in .env and .env.example; never echo values. To check that the URL's password matches POSTGRES_PASSWORD, use a script that prints only "match" or "mismatch".
- Rewrite DATABASE_URL in place from POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_SERVER, POSTGRES_PORT and POSTGRES_DB, whichever the backend settings in backend/app/core/config.py actually use.
- Keep a backup copy as .env.bak and tell me it exists.
- Then run `docker compose up -d db` and `cd backend && uv run bash scripts/prestart.sh`, and report whether migrations apply.

If the db volume was created with a different password from the one in .env, tell me. Offer two options: reset the volume (this destroys local data, so I must approve it), or change .env to match.

No commits.
```
