import { FiPauseCircle, FiRefreshCcw, FiRotateCcw } from "react-icons/fi"
import type { IngestionRunDetail, IngestionRunPublic } from "@/client"
import {
  formatMetric,
  labelize,
  shortId,
} from "@/components/Constitution/admin/format"
import {
  EmptyState,
  ListState,
  Panel,
  SmallStat,
  StatusPill,
} from "@/components/Constitution/admin/ui"
import type { RunEventsStreamState } from "@/components/Constitution/admin/useRunEventsStream"
import { SquircleButton } from "@/components/Constitution/primitives"
import { cn } from "@/lib/utils"

export function RunWorkspace({
  runs,
  selected,
  selectedId,
  detail,
  eventStream,
  isLoading,
  isMutating,
  onSelect,
  onControl,
}: {
  runs: IngestionRunPublic[]
  selected?: IngestionRunPublic | IngestionRunDetail
  selectedId?: string
  detail?: IngestionRunDetail
  eventStream: RunEventsStreamState
  isLoading: boolean
  isMutating: boolean
  onSelect: (id: string) => void
  onControl: (
    action: "retry" | "cancel" | "resume",
    run: IngestionRunPublic | IngestionRunDetail,
    reason?: string,
  ) => void
}) {
  const canResume = selected ? canResumeRun(selected) : false
  const canRetry = selected ? canRetryRun(selected) : false
  const canCancel = selected ? canCancelRun(selected) : false

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
      <Panel title="Runs" count={runs.length}>
        <ListState isLoading={isLoading} isEmpty={!runs.length} />
        <div className="grid gap-2">
          {runs.map((run) => (
            <button
              className={cn(
                "sq-md border p-3 text-left transition",
                run.id === selectedId
                  ? "border-primary bg-accent"
                  : "border-border bg-card hover:border-primary/30",
              )}
              aria-label={`${labelize(run.current_stage)} ${labelize(
                run.status,
              )}`}
              key={run.id}
              onClick={() => onSelect(run.id)}
              type="button"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold">
                    {labelize(run.current_stage)}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {shortId(run.id)}
                  </p>
                </div>
                <StatusPill status={run.status} />
              </div>
            </button>
          ))}
        </div>
      </Panel>

      <Panel title="Run detail">
        {selected ? (
          <div className="grid gap-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-lg font-bold">
                  {labelize(selected.current_stage)}
                </p>
                <p className="text-sm text-muted-foreground">
                  {selected.pipeline_version} · {shortId(selected.id)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <SquircleButton
                  disabled={isMutating || !canResume}
                  onClick={() => onControl("resume", selected)}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  <FiRotateCcw className="size-4" aria-hidden />
                  Resume
                </SquircleButton>
                <SquircleButton
                  disabled={isMutating || !canRetry}
                  onClick={() => onControl("retry", selected)}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  <FiRefreshCcw className="size-4" aria-hidden />
                  Retry
                </SquircleButton>
                <SquircleButton
                  disabled={isMutating || !canCancel}
                  onClick={() =>
                    onControl("cancel", selected, "Operator cancelled run")
                  }
                  size="sm"
                  type="button"
                  variant="danger"
                >
                  <FiPauseCircle className="size-4" aria-hidden />
                  Cancel
                </SquircleButton>
              </div>
            </div>

            <RunEventStreamStatus stream={eventStream} />

            <div className="grid gap-3 md:grid-cols-4">
              <SmallStat label="Status" value={labelize(selected.status)} />
              <SmallStat
                label="Pages"
                value={formatMetric(selected.expected_page_count)}
              />
              <SmallStat
                label="Completed"
                value={`${selected.completed_units}/${selected.total_units}`}
              />
              <SmallStat
                label="Failed"
                value={formatMetric(selected.failed_units)}
              />
            </div>

            {detail?.steps.length ? (
              <div className="grid gap-2">
                {detail.steps.map((step) => (
                  <div
                    className="grid gap-3 border-border border-b py-3 last:border-b-0 md:grid-cols-[1fr_auto]"
                    key={step.id}
                  >
                    <div>
                      <p className="text-sm font-semibold">
                        {labelize(step.stage)}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Attempts {step.attempt_count} · Units{" "}
                        {step.completed_units}/{step.total_units}
                      </p>
                    </div>
                    <StatusPill status={step.status} />
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState text="No stage records yet." />
            )}

            {detail?.events.length ? (
              <EventLog events={detail.events} />
            ) : (
              <EmptyState text="No run events yet." />
            )}
          </div>
        ) : (
          <EmptyState text="No ingestion run selected." />
        )}
      </Panel>
    </div>
  )
}

function EventLog({
  events,
}: {
  events: NonNullable<IngestionRunDetail["events"]>
}) {
  return (
    <div className="grid gap-2">
      {events.map((event) => (
        <div
          className="grid gap-2 border-border border-b py-3 last:border-b-0 md:grid-cols-[96px_1fr]"
          key={event.id}
        >
          <span className="text-xs font-bold text-muted-foreground">
            #{event.sequence}
          </span>
          <div>
            <p className="text-sm font-semibold">
              {labelize(event.event_type)}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {event.message}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}

function RunEventStreamStatus({ stream }: { stream: RunEventsStreamState }) {
  return (
    <div
      aria-label="Run event stream status"
      aria-live="polite"
      className="sq-md flex flex-wrap items-center gap-3 border border-border bg-background p-3 text-sm"
      role="status"
    >
      <StatusPill status={stream.status} />
      <span className="text-muted-foreground">
        {runEventStreamLabel(stream)}
      </span>
    </div>
  )
}

function runEventStreamLabel(stream: RunEventsStreamState): string {
  if (stream.status === "connecting") {
    return "Connecting to live events."
  }
  if (stream.status === "streaming") {
    return stream.lastEventId
      ? `Live events streaming from #${stream.lastEventId}.`
      : "Live events streaming."
  }
  if (stream.status === "reconnecting") {
    return "Live events reconnecting; checking for updates."
  }
  if (stream.status === "polling") {
    return "Live events unavailable; checking for updates."
  }
  return "No live run selected."
}

function canResumeRun(run: IngestionRunPublic | IngestionRunDetail): boolean {
  return run.status === "cancelled"
}

function canRetryRun(run: IngestionRunPublic | IngestionRunDetail): boolean {
  return run.status === "failed"
}

function canCancelRun(run: IngestionRunPublic | IngestionRunDetail): boolean {
  return !["published", "cancelled"].includes(run.status)
}
