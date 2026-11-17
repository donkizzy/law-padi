import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import {
  AdminService,
  type IngestionEventPublic,
  type IngestionRunDetail,
} from "@/client"
import { adminKeys, createInvalidationBatcher } from "@/lib/admin-queries"

export type RunEventsStreamState = {
  events: IngestionEventPublic[]
  lastEventId?: string
  status: "idle" | "connecting" | "streaming" | "reconnecting" | "polling"
}

export function useRunEventsStream(runId?: string): RunEventsStreamState {
  const queryClient = useQueryClient()
  const [streamState, setStreamState] = useState<RunEventsStreamState>({
    events: [],
    status: "idle",
  })

  useEffect(() => {
    if (!runId) {
      setStreamState({ events: [], status: "idle" })
      return
    }

    const controller = new AbortController()
    const refreshes = createInvalidationBatcher(queryClient)
    let isCurrentRun = true

    setStreamState({ events: [], status: "connecting" })

    const consumeEvents = async () => {
      try {
        const stream = await AdminService.streamIngestionRunEvents({
          onSseError: () => {
            if (!isCurrentRun) return
            setStreamState((current) => ({
              ...current,
              status: current.lastEventId ? "reconnecting" : "polling",
            }))
          },
          path: { run_id: runId },
          signal: controller.signal,
          sseDefaultRetryDelay: 1000,
          sseMaxRetryDelay: 5000,
        })

        for await (const event of stream.stream) {
          if (!isCurrentRun) break
          const runEvent = parseRunEvent(event)
          if (!runEvent) continue
          setStreamState((current) => ({
            events: mergeRunEvents(current.events, [runEvent]),
            lastEventId: String(runEvent.sequence),
            status: "streaming",
          }))
          // The event is added to the cached run, and the figures only the
          // server knows (status, progress) are refreshed once per second.
          queryClient.setQueryData<IngestionRunDetail>(
            adminKeys.run(runId),
            (current) =>
              current && {
                ...current,
                events: mergeRunEvents(current.events, [runEvent]),
              },
          )
          refreshes.invalidate(adminKeys.runs(), adminKeys.run(runId))
          if (
            runEvent.stage === "profiling" ||
            runEvent.stage === "awaiting_page_confirmation"
          )
            refreshes.invalidate(adminKeys.runPages(runId))
        }

        if (isCurrentRun) {
          setStreamState((current) => ({
            ...current,
            status: "polling",
          }))
        }
      } catch {
        if (!controller.signal.aborted && isCurrentRun) {
          setStreamState((current) => ({
            ...current,
            status: "polling",
          }))
        }
      }
    }

    void consumeEvents()

    return () => {
      isCurrentRun = false
      controller.abort()
      refreshes.cancel()
    }
  }, [queryClient, runId])

  return streamState
}

function parseRunEvent(value: unknown): IngestionEventPublic | null {
  if (!value || typeof value !== "object") return null
  const candidate = value as Partial<IngestionEventPublic>
  if (
    typeof candidate.id !== "string" ||
    typeof candidate.run_id !== "string" ||
    typeof candidate.sequence !== "number" ||
    typeof candidate.event_type !== "string" ||
    typeof candidate.message !== "string"
  ) {
    return null
  }
  return candidate as IngestionEventPublic
}

export function mergeRunEvents(
  existing: IngestionEventPublic[],
  incoming: IngestionEventPublic[],
): IngestionEventPublic[] {
  const events = new Map<string, IngestionEventPublic>()
  for (const event of [...existing, ...incoming]) {
    events.set(event.id || `${event.sequence}`, event)
  }
  return [...events.values()].sort(
    (left, right) => left.sequence - right.sequence,
  )
}
