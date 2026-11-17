import type { ReactNode, RefObject } from "react"
import { useMemo } from "react"
import { useTranslation } from "react-i18next"
import type { CitationOutcome, EvidenceItem, MessagePublic } from "@/client"
import { AnswerBoundary } from "@/components/Constitution/AnswerBoundary"
import { AnswerFeedback } from "@/components/Constitution/AnswerFeedback"
import { AnswerLoading } from "@/components/Constitution/AnswerLoading"
import {
  AnswerView,
  LookupGaps,
  withoutContained,
} from "@/components/Constitution/chat/AnswerView"
import type { Progress } from "@/components/Constitution/chat/useAnswerStream"
import { InlineAction } from "@/components/Constitution/primitives"
import { type ExplanationAnswer, parseAnswer } from "@/lib/answer"

export function PendingAnswer({
  progress,
  sources,
  outcomes,
}: {
  progress: Progress | null
  sources: EvidenceItem[]
  outcomes: CitationOutcome[]
}) {
  const { t } = useTranslation(["chat", "common"])
  const reading = withoutContained(sources).slice(0, 4)
  return (
    <section aria-label={t("pending.label")} className="grid gap-4">
      <LookupGaps outcomes={outcomes} />
      <div className="grid gap-3 py-4">
        <AnswerLoading
          progress={progress ?? "finding"}
          label={t(`progress.${progress ?? "finding"}`)}
        />
        {reading.length > 0 && (
          <p className="text-label font-normal text-muted-foreground">
            {t("pending.reading", {
              sources: reading
                .map((item) =>
                  item.title
                    ? `${item.citation} (${item.title})`
                    : item.citation,
                )
                .join(", "),
            })}
          </p>
        )}
      </div>
    </section>
  )
}

export function MessageView({
  message,
  onSelect,
  onAsk,
  conversationId,
}: {
  message: MessagePublic
  conversationId?: string
  onSelect: (item: EvidenceItem) => void
  onAsk?: (question: string) => void
}) {
  const { t } = useTranslation(["chat", "common"])
  const answer = useMemo(
    () => parseAnswer(message.answer_content),
    [message.answer_content],
  )
  if (message.role === "user")
    return (
      <div className="ml-auto max-w-[90%] sq-lg bg-secondary px-4 py-3 text-body">
        {message.content}
      </div>
    )
  return answer ? (
    <div data-answer-start="" className="scroll-mt-24">
      <AnswerBoundary resetKey={message.answer_content}>
        <AnswerView answer={answer} onAsk={onAsk} onSelect={onSelect} />
      </AnswerBoundary>
      {conversationId && (
        <AnswerFeedback message={message} conversationId={conversationId} />
      )}
    </div>
  ) : (
    <p className="text-body text-muted-foreground" role="alert">
      {t("answer.loadFailed")}
    </p>
  )
}

type MessageListProps = {
  listRef: RefObject<HTMLDivElement | null>
  hasOlder: boolean
  loadingOlder: boolean
  onLoadOlder: () => void
  messages: MessagePublic[]
  conversationId?: string
  latestAssistantId?: string
  activeRunId: string | null
  onAsk: (question: string) => void
  onSelect: (item: EvidenceItem) => void
  pendingQuestion: string
  showPendingQuestion: boolean
  awaitingAnswer: boolean
  liveAnswer: ExplanationAnswer | null
  showLiveAnswer: boolean
  outcomes: CitationOutcome[]
  progress: Progress | null
  sources: EvidenceItem[]
  /** Run status and request errors, shown after the answers. */
  children?: ReactNode
}

/** The conversation's messages, the question being answered and its live answer. */
export function MessageList({
  listRef,
  hasOlder,
  loadingOlder,
  onLoadOlder,
  messages,
  conversationId,
  latestAssistantId,
  activeRunId,
  onAsk,
  onSelect,
  pendingQuestion,
  showPendingQuestion,
  awaitingAnswer,
  liveAnswer,
  showLiveAnswer,
  outcomes,
  progress,
  sources,
  children,
}: MessageListProps) {
  const { t } = useTranslation(["chat", "common"])
  return (
    <div ref={listRef} className="grid flex-1 content-start gap-6">
      {hasOlder && (
        <InlineAction
          disabled={loadingOlder}
          onClick={onLoadOlder}
          type="button"
        >
          {loadingOlder
            ? t("common:status.loading")
            : t("conversation.loadOlder")}
        </InlineAction>
      )}
      {messages.map((message) => (
        <MessageView
          key={message.id}
          message={message}
          conversationId={conversationId}
          onAsk={
            message.id === latestAssistantId && !activeRunId ? onAsk : undefined
          }
          onSelect={onSelect}
        />
      ))}
      {showPendingQuestion && (
        <div className="ml-auto max-w-[90%] sq-lg bg-secondary px-4 py-3 text-sm leading-6">
          {pendingQuestion}
        </div>
      )}
      {awaitingAnswer && !showLiveAnswer && (
        <PendingAnswer
          outcomes={outcomes}
          progress={progress}
          sources={sources}
        />
      )}
      {showLiveAnswer && liveAnswer && (
        <div data-answer-start="" className="scroll-mt-24">
          <AnswerBoundary resetKey={liveAnswer}>
            <AnswerView
              answer={liveAnswer}
              onAsk={activeRunId ? undefined : onAsk}
              onSelect={onSelect}
            />
          </AnswerBoundary>
        </div>
      )}
      {children}
    </div>
  )
}
