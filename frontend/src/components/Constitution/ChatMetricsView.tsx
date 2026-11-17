import { useQuery } from "@tanstack/react-query"
import { ConversationsService } from "@/client"
import { conversationHeaders } from "@/hooks/useConversations"
import { InlineAction } from "./primitives"

export function ChatMetricsView() {
  const metrics = useQuery({
    queryKey: ["chat-metrics"],
    queryFn: async ({ signal }) =>
      (
        await ConversationsService.readChatMetrics({
          headers: conversationHeaders(),
          signal,
        })
      ).data,
    staleTime: 30_000,
    retry: false,
  })
  if (metrics.isPending)
    return <p role="status">Loading answer quality signals…</p>
  if (metrics.isError)
    return (
      <p role="alert">
        Quality signals couldn't load.{" "}
        <InlineAction type="button" onClick={() => void metrics.refetch()}>
          Try again
        </InlineAction>
      </p>
    )
  return (
    <div className="grid gap-3 text-body">
      <p className="text-muted-foreground">
        Last 24 hours. These counts measure completion and usefulness; they do
        not certify legal accuracy.
      </p>
      <dl className="grid gap-x-5 gap-y-2 sm:grid-cols-2">
        <dt>Accepted questions</dt>
        <dd>{metrics.data.accepted_questions}</dd>
        <dt>Finished answers</dt>
        <dd>{metrics.data.finished_answers}</dd>
        <dt>Plain-English answers</dt>
        <dd>{metrics.data.explained_answers}</dd>
        <dt>Average time to finish</dt>
        <dd>
          {metrics.data.average_finish_ms === null
            ? "No completed runs"
            : `${(metrics.data.average_finish_ms / 1000).toFixed(1)} seconds`}
        </dd>
        <dt>Helpful / not helpful</dt>
        <dd>
          {metrics.data.helpful_ratings} / {metrics.data.unhelpful_ratings}
        </dd>
      </dl>
      <details>
        <summary className="cursor-pointer">Answer outcomes</summary>
        <ul className="mt-2 grid gap-1">
          {Object.entries(metrics.data.outcomes).map(([label, count]) => (
            <li key={label}>
              {label.replace(/_/g, " ")}: {count}
            </li>
          ))}
        </ul>
      </details>
    </div>
  )
}
