# Decision records

Short records of decisions that shaped the system. Each states the context, the
decision, its consequences and its status. The architecture they fit into is
described in [`../architecture.md`](../architecture.md).

| No. | Decision |
| --- | --- |
| [0001](0001-postgres-pgvector-retrieval.md) | Keep retrieval in PostgreSQL with pgvector rather than a separate vector store |
| [0002](0002-evidence-boundary-and-server-citations.md) | Answers cite supplied evidence only; citations are built by the server; validation fails closed |
| [0003](0003-english-core-translated-edges.md) | Reader languages translate the question in and the verified answer out; everything else runs in English |
| [0004](0004-release-pinned-corpus.md) | The corpus is published as immutable releases, and conversations pin the release they started on |
| [0005](0005-render-cloudflare-neon-hosting.md) | Host on Render, a Cloudflare Worker and Neon instead of Cloud Run |
| [0006](0006-reserve-then-settle-spend-ledger.md) | Reserve the worst-case cost of every paid call before making it, and settle afterwards |
