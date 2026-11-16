# Free-tier deployment

The beta runs on a Cloudflare Worker, one Render Free web service, Neon
PostgreSQL and private R2 object storage. The API process hosts a request-woken
chat worker; PostgreSQL retains pending runs, leases, events and spend
reservations across service restarts. Ingestion remains an administrative
operation outside the public runtime.

The [deployment overview](../deployment/README.md) links the operational
runbooks and the archived, unused deployment proposal. Use
[`render.yaml`](../render.yaml) for production settings, including concurrency,
AI budgets and query embeddings, rather than copying values from a planning
document. Check each provider's current account allowances before deployment;
free hosting does not make model calls or excess usage free.
