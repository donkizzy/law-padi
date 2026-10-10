# Isolated chat infrastructure load test — 8 October 2026

The controlled local test **passed the infrastructure target**. It used a disposable PostgreSQL database restored from the verified local corpus dump, one API process on port 18000, one chat worker configured for 1,000 concurrent tasks, and the private provider simulator with a 30-second delay per call. The real `app` database and DeepSeek API were not used.

| Measure | Observed |
| --- | ---: |
| Guest conversations created | 1,000 |
| Generation submissions accepted | 1,000 |
| Active runs in the shared capacity row | 1,000 |
| Simulated provider calls in flight | 1,000 |
| Peak simultaneous SSE connections | 1,000 |
| Terminal answer events received | 1,000 |
| Completed, validated runs persisted | 1,000 |
| Client errors | 0 |
| P95 admission latency | 2,905.8 ms |
| Total elapsed time | 80.5 seconds |

The latest 1,000 runs produced 2,000 simulator reservations, 200,000 prompt tokens and 80,000 completion tokens as reported by the simulator. The accounting ledger settled 582,000 micro-USD ($0.582 at configured rates) and retained zero reservations. P95 stored stage times were 23 ms for retrieval, 30,054 ms for generation, 30,056 ms for verification, and 60,169 ms total. No run used lexical fallback. The simulator always approves grounding, so these results measure infrastructure and accounting behavior, not legal answer quality.

The trial found two bottlenecks before passing. The default API database pool of 15 connections timed out under burst traffic; the API now defaults to 40, with smaller worker pools configured in Compose. Response construction after commit opened new transactions and held connections during conversation creation and submission; those responses are now built before commit. The client uses bounded submission fan-out, idempotent retries, and `Last-Event-ID` SSE replay. Separate trial passes confirmed 300 concurrent conversation creations in 3.3 seconds and 1,000 active provider sockets. Keep API, worker, and ingestion pool totals below PostgreSQL's connection limit when scaling replicas.

**Rollout status:** live DeepSeek validation, provider quota approval for 1,000 concurrent calls, and human review of the 200-case answer set are still pending. Public generation remains disabled.
