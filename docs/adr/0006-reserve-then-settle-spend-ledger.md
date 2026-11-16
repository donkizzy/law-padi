# 0006. Reserve the worst-case cost of every paid call, then settle

Status: accepted. In place since the first generated explanations (October 2026).

## Context

Every answer makes several paid model calls (understanding for non-English
questions, drafting, verification, translation and judging). Provider calls can
time out after the provider has already charged for them, several processes may
generate at once, and the service is public. Budgets must hold even when calls
fail in the middle.

## Decision

`backend/app/chat/budget.py`:

- Before each call, reserve its maximum possible cost (prompt size and the
  output-token cap at configured prices) against a Lagos-day and a calendar-month
  ledger. The reservation runs under a row lock, so concurrent workers cannot
  overspend.
- After the call, settle the reservation with the usage the provider reports.
- If the outcome is uncertain (for example a timeout after dispatch), keep the
  reservation instead of releasing it, so possible charges stay counted until
  they are reconciled.
- Search-query translation has its own daily sub-budget.
- Per-guest and per-account daily and one-minute limits are enforced separately
  at admission (`backend/app/api/routes/conversations.py`).

## Consequences

- Ledgered spend stays within the configured limits under concurrency and
  provider failures, provided the configured prices match the provider's. The
  limits err towards refusing answers.
- Reservation rows outlive conversation deletion so in-flight calls can still
  settle.
- Query embeddings are billed by a different provider and are bounded by a daily
  request limit (`QUERY_EMBEDDING_DAILY_LIMIT`), not by this ledger.
