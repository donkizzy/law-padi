# Documentation

Start with [`architecture.md`](architecture.md).

**Design**

- [`architecture.md`](architecture.md): components, data model, ingestion,
  retrieval and answer pipelines, releases, languages, deployment.
- [`adr/`](adr/README.md): decision records.
- [`evaluation.md`](evaluation.md): datasets, results and the limits of the
  method.

**Operating**

- [`runbooks/railway-migration.md`](runbooks/railway-migration.md): moving the API and database to Railway, with the cost estimate; the services themselves are in [`deployment/railway/README.md`](../deployment/railway/README.md).
- [`runbooks/render.md`](runbooks/render.md): the Render service, until the Railway cutover retires it.
- [`runbooks/release.md`](runbooks/release.md): code and corpus releases.
- [`runbooks/backup-restore.md`](runbooks/backup-restore.md): backups and restore checks.
- [`runbooks/ingestion.md`](runbooks/ingestion.md): turning a source PDF into a release.
- [`runbooks/observability.md`](runbooks/observability.md): request ids, logs, probes, heartbeats and Sentry.
- [`runbooks/branch-protection.md`](runbooks/branch-protection.md): required checks and branch rules to apply on GitHub.
- [`evidence-chat-rollout.md`](evidence-chat-rollout.md): chat controls, the
  answer-quality gate and the recorded launch exception.
- [`docker-images.md`](docker-images.md): what each image contains.
- [`seo-and-ai-discovery.md`](seo-and-ai-discovery.md): public pages and crawler access.

**Plans and reviews in progress**

- [`multilingual-evaluation-plan.md`](multilingual-evaluation-plan.md) and
  [`reader-language-review-checklist.md`](reader-language-review-checklist.md):
  gates for the reader languages.

**Contributing**

- [`development.md`](development.md): workers, Compose, tests and generated code.

Dated phase reports and working notes were removed from the tree; the full set
is preserved at git tag `archive/pre-public-cleanup`.
