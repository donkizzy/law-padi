import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { FiSearch } from "react-icons/fi"
import {
  AdminService,
  type CorpusReleasePublic,
  type EmbeddingBenchmarkPublic,
} from "@/client"
import {
  formatMetric,
  formatPercent,
  labelize,
} from "@/components/Constitution/admin/format"
import {
  ListState,
  Panel,
  SmallStat,
  StatusPill,
} from "@/components/Constitution/admin/ui"
import { SquircleButton } from "@/components/Constitution/primitives"
import { Input } from "@/components/ui/input"
import { adminKeys } from "@/lib/admin-queries"
import { cn } from "@/lib/utils"

export function BenchmarkWorkspace({
  releases,
  selectedId,
  benchmark,
  isLoading,
  onSelect,
}: {
  releases: CorpusReleasePublic[]
  selectedId?: string
  benchmark?: EmbeddingBenchmarkPublic
  isLoading: boolean
  onSelect: (id: string) => void
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
      <Panel title="Release">
        <div className="grid gap-2">
          {releases.map((release) => (
            <button
              className={cn(
                "sq-md border p-3 text-left transition",
                release.id === selectedId
                  ? "border-primary bg-accent"
                  : "border-border bg-card hover:border-primary/30",
              )}
              key={release.id}
              onClick={() => onSelect(release.id)}
              type="button"
            >
              <p className="text-sm font-bold">{release.version}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {labelize(release.status)}
              </p>
            </button>
          ))}
        </div>
      </Panel>
      <Panel title="Embedding benchmarks">
        <p className="mb-3 text-xs text-muted-foreground">
          Winner needs Recall@10 ≥ 95%; ties break on nDCG@10, then cost and p95
          latency. Both dense candidates share the sparse_legal baseline.
        </p>
        <ListState
          isEmpty={!benchmark?.results.length}
          isLoading={isLoading}
          text="No benchmark results yet."
        />
        <div className="grid gap-2">
          {benchmark?.results.map((result) => (
            <div
              className="sq-md border border-border bg-background p-4"
              key={result.profile_id}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold">{result.model_name}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {labelize(result.provider)}
                  </p>
                </div>
                <StatusPill status={result.status} />
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-4">
                <SmallStat
                  label="Recall@10"
                  value={formatPercent(result.recall_at_10)}
                />
                <SmallStat
                  label="nDCG@10"
                  value={formatPercent(result.ndcg_at_10)}
                />
                <SmallStat
                  label="P95"
                  value={
                    result.p95_latency_ms
                      ? `${Math.round(result.p95_latency_ms)} ms`
                      : "Pending"
                  }
                />
                <SmallStat
                  label="Selected"
                  value={result.selected_for_release ? "Yes" : "No"}
                />
              </div>
            </div>
          ))}
        </div>
      </Panel>
      <OcrBenchmarkPanel />
    </div>
  )
}

function OcrBenchmarkPanel() {
  const [datasetVersion, setDatasetVersion] = useState("")
  const infoQuery = useQuery({
    queryKey: adminKeys.ocrBenchmark(datasetVersion),
    queryFn: async () =>
      (
        await AdminService.readOcrBenchmark({
          path: { dataset_version: datasetVersion },
        })
      ).data,
    enabled: Boolean(datasetVersion.trim()),
    retry: false,
  })
  return (
    <Panel title="OCR benchmarks">
      <p className="mb-3 text-xs text-muted-foreground">
        Compare Google Document AI vs Azure Document Intelligence on the same
        versioned OCR_PAGE dataset. The winner is activated via
        MANAGED_OCR_PROVIDER configuration.
      </p>
      <div className="grid gap-2 sm:grid-cols-[2fr_auto]">
        <Input
          aria-label="OCR benchmark dataset version"
          onChange={(event) => setDatasetVersion(event.target.value)}
          placeholder="e.g. ocr-gold-v1"
          value={datasetVersion}
        />
        <SquircleButton
          disabled={!datasetVersion.trim()}
          onClick={() => infoQuery.refetch()}
          type="button"
          variant="outline"
        >
          <FiSearch className="size-4" aria-hidden />
          Load dataset
        </SquircleButton>
      </div>
      {infoQuery.data ? (
        <p className="mt-3 text-sm text-muted-foreground">
          {infoQuery.data.sample_count} pages ·{" "}
          {infoQuery.data.active_dataset_items} active items
          {infoQuery.data.winner ? ` · winner ${infoQuery.data.winner}` : ""}
        </p>
      ) : null}
      {infoQuery.data?.providers?.length ? (
        <div className="mt-3 grid gap-2">
          {infoQuery.data.providers.map((result) => (
            <div
              className="sq-md border border-border bg-background p-4"
              key={result.provider}
            >
              <p className="text-sm font-bold">{result.provider}</p>
              <div className="mt-3 grid gap-3 md:grid-cols-4">
                <SmallStat
                  label="Char accuracy"
                  value={formatPercent(result.mean_character_accuracy)}
                />
                <SmallStat
                  label="Failures"
                  value={formatMetric(result.failure_count)}
                />
                <SmallStat
                  label="Cost"
                  value={
                    result.total_cost_usd != null
                      ? `$${result.total_cost_usd}`
                      : "Pending"
                  }
                />
                <SmallStat
                  label="Mean ms"
                  value={formatMetric(result.mean_timing_ms)}
                />
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </Panel>
  )
}
