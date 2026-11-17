import type { QueryClient, QueryKey } from "@tanstack/react-query"
import type {
  AdminMetrics,
  IngestionRunPublic,
  IngestionRunStatus,
} from "@/client"

/** Query keys of the legal operations screen, from the broadest to the narrowest. */
export const adminKeys = {
  all: ["admin"] as const,
  metrics: () => ["admin", "metrics"] as const,
  alerts: () => ["admin", "alerts"] as const,
  roles: () => ["admin", "my-roles"] as const,
  runs: () => ["admin", "ingestion-runs"] as const,
  /** The run and, below it, its pages. */
  run: (id: string | undefined) => ["admin", "ingestion-runs", id] as const,
  runPages: (id: string | undefined) =>
    ["admin", "ingestion-runs", id, "pages"] as const,
  reviews: () => ["admin", "review-items"] as const,
  releases: () => ["admin", "corpus-releases"] as const,
  /** The release and, below it, its manifest and publication evidence. */
  release: (id: string | undefined) =>
    ["admin", "corpus-releases", id] as const,
  releaseManifest: (id: string | undefined) =>
    ["admin", "corpus-releases", id, "manifest"] as const,
  releaseEvidence: (id: string | undefined) =>
    ["admin", "corpus-releases", id, "publication-evidence"] as const,
  benchmark: (releaseId: string | undefined) =>
    ["admin", "embedding-benchmarks", releaseId] as const,
  auditEvents: (releaseId: string | undefined) =>
    ["admin", "audit-events", releaseId] as const,
  ocrBenchmark: (datasetVersion: string) =>
    ["admin", "ocr-benchmarks", datasetVersion] as const,
}

// Runs the pipeline is working on. The others wait for a person or are over.
const workingStatuses: ReadonlySet<IngestionRunStatus> = new Set([
  "queued",
  "running",
  "ready_to_embed",
  "indexing",
  "ready_to_publish",
  "publishing",
])

/** Whether the pipeline has work in progress that the screen should follow. */
export function hasActiveWork(
  metrics: AdminMetrics | undefined,
  runs: IngestionRunPublic[],
): boolean {
  return (
    Boolean(metrics && (metrics.active_runs > 0 || metrics.queue_depth > 0)) ||
    runs.some((run) => workingStatuses.has(run.status))
  )
}

/**
 * Options for a query the screen keeps current. A tab that is not in front
 * does not poll (`refetchIntervalInBackground`), and coming back to it
 * refreshes anything older than a few seconds.
 */
export const liveQuery = {
  staleTime: 4_000,
  refetchOnWindowFocus: true,
  refetchIntervalInBackground: false,
} as const

// The part of a query that pacing reads; any query satisfies it.
type PacedQuery = {
  state: { dataUpdatedAt: number; data: unknown; status: string }
}

type Seen = { updatedAt: number; data: unknown; unchanged: number }
const seen = new WeakMap<object, Seen>()

/**
 * A `refetchInterval` that polls only while `active`, starting at `baseMs`
 * and doubling (up to `maxMs`) for every poll that returned the same data. A
 * poll that returned something new, or a failing query, resets it.
 */
export function pollWhile(active: boolean, baseMs: number, maxMs: number) {
  return (query: PacedQuery): number | false => {
    if (!active) return false
    const { dataUpdatedAt, data, status } = query.state
    const previous = seen.get(query)
    let unchanged = previous?.unchanged ?? 0
    if (previous && previous.updatedAt !== dataUpdatedAt)
      unchanged = Object.is(previous.data, data) ? unchanged + 1 : 0
    seen.set(query, { updatedAt: dataUpdatedAt, data, unchanged })
    if (status === "error") return maxMs
    return Math.min(maxMs, baseMs * 2 ** unchanged)
  }
}

/**
 * Collects invalidations and sends each distinct key once per `delayMs`, so a
 * burst of stream events refetches a query once instead of once per event.
 * Keys are matched exactly: a run's detail never refetches its pages.
 */
export function createInvalidationBatcher(
  queryClient: QueryClient,
  delayMs = 1_000,
) {
  const pending = new Map<string, QueryKey>()
  let timer: ReturnType<typeof setTimeout> | undefined
  return {
    invalidate(...keys: QueryKey[]) {
      for (const key of keys) pending.set(JSON.stringify(key), key)
      if (timer !== undefined) return
      timer = setTimeout(() => {
        timer = undefined
        const batch = [...pending.values()]
        pending.clear()
        for (const queryKey of batch)
          void queryClient.invalidateQueries({ queryKey, exact: true })
      }, delayMs)
    },
    cancel() {
      if (timer !== undefined) clearTimeout(timer)
      timer = undefined
      pending.clear()
    },
  }
}
