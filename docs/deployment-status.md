# Deployment status — 16 October 2026

The backend is live on **Render Free** in Virginia:

- Service: `constitution-ng-api` (`srv-db8u1gavcj2c73b7h75g`).
- Health endpoint: <https://constitution-ng-api.onrender.com/healthz>.
- Initial deployed commit: `f6512e505d733744b57f4985b6b569f24bb25850`.
- Packaged revision: `source-f294f6a729619518`; prompt `constitution-english-v8`.
- Repository branch: `master`; automatic deployment: **After CI Checks Pass**.
- Database: Neon Free PostgreSQL 18; source PDFs: private Cloudflare R2.

Live checks passed for health, protected runtime metadata, corpus release reads,
Section 37 lookup, lexical search (10 results), and a signed PDF redirect.
Direct API calls without the origin proxy credential return 403. No paid AI was
called during these checks. Local frontend formatting/build, backend types/lint,
deployment helper tests, proxy tests and the production container build pass.

## GitHub CI account blocker

GitHub accepted the grouped commits, but Actions did not start any jobs.
[The initial run](https://github.com/donkizzy/law-padi/actions/runs/38873722237)
reports: “The job was not started because recent account payments have failed or
your spending limit needs to be increased.” The account owner must resolve this
with GitHub before hosted CI can run. No payment method, spending limit or
repository visibility was changed. Render remains configured to wait for checks
on future pushes. Its first deployment was created manually after local checks.

## Public launch remains pending

AI generation is disabled, its kill switch is on, and provider-capacity approval
is false. The Cloudflare public frontend has **not** been published because AI
chat is required at launch. The preceding capture collected 170 of 200 cases
against an earlier packaged revision; it does not satisfy the current launch
gate or the required human grounding review. Do not treat a green CI build as
approval to enable AI. Follow [the rollout controls](evidence-chat-rollout.md).

The $5 monthly AI cap includes the evaluation ledger transferred to Neon:
$3.249977 recorded spend and $0.069612 held across four unresolved reservations.
All 1,212 reservation identities were preserved, including prior history, and
generation remains disabled. The guarded, transactional prelaunch transfer is in
`deployment/render/sync_spend.py`; its private report is excluded from Git.
Automatic backups and working password-recovery email are also unfinished.
Backup scripts are prepared, but the GitHub schedule and bucket-scoped backup
credentials have not been activated. No GCP runtime resources were provisioned;
its billing activation remains unused.

See [the Render runbook](../deployment/render/README.md) for deployment and
recovery. Credentials, database dumps, local captures and account setup
screenshots remain outside Git.
