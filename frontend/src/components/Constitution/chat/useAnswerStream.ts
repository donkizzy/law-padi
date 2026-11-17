import { useQueryClient } from "@tanstack/react-query"
import type { Dispatch, RefObject, SetStateAction } from "react"
import { useEffect } from "react"
import type {
  CitationOutcome,
  ConversationDetail,
  EvidenceItem,
} from "@/client"
import { ConversationsService } from "@/client"
import type { useChatRequestScope } from "@/hooks/useChatRequestScope"
import { conversationHeaders } from "@/hooks/useConversations"
import {
  type ExplanationAnswer,
  parseAnswer,
  parseCitationOutcomes,
  parseEvidence,
} from "@/lib/answer"

export type Progress =
  | "finding"
  | "writing"
  | "checking"
  | "translating"
  | "reconnecting"
  | "connectionLost"
  | "interrupted"
  | "stopping"

type AnswerStreamOptions = {
  conversationId: string | undefined
  activeRunId: string | null
  /** Bumped by the reader's reconnect action to open the stream again. */
  streamAttempt: number
  openSources: boolean
  beginRequest: ReturnType<typeof useChatRequestScope>
  pendingKey: RefObject<unknown>
  setProgress: Dispatch<SetStateAction<Progress | null>>
  setSources: Dispatch<SetStateAction<EvidenceItem[]>>
  setOutcomes: Dispatch<SetStateAction<CitationOutcome[]>>
  setLiveAnswer: Dispatch<SetStateAction<ExplanationAnswer | null>>
  setSelectedEvidence: Dispatch<SetStateAction<EvidenceItem | null>>
  setRunId: Dispatch<SetStateAction<string | null>>
  setPendingQuestion: Dispatch<SetStateAction<string>>
  setStreamError: Dispatch<SetStateAction<boolean>>
}

/**
 * Follows the server-sent events of the conversation's active run, moving the
 * page's progress, sources and live answer along, and falls back to the stored
 * conversation when the stream ends without a terminal event.
 */
export function useAnswerStream({
  conversationId,
  activeRunId,
  streamAttempt,
  openSources,
  beginRequest,
  pendingKey,
  setProgress,
  setSources,
  setOutcomes,
  setLiveAnswer,
  setSelectedEvidence,
  setRunId,
  setPendingQuestion,
  setStreamError,
}: AnswerStreamOptions) {
  const queryClient = useQueryClient()
  // The setters and the ref keep their identity across renders, so only the
  // run, the conversation, the reconnect count and the preference reopen it.
  useEffect(() => {
    if (!conversationId || !activeRunId) return
    const scope = beginRequest()
    let terminal = false
    if (streamAttempt > 0) setProgress("reconnecting")
    void (async () => {
      try {
        const { stream } = await ConversationsService.conversationEvents({
          path: { conversation_id: conversationId },
          query: { run_id: activeRunId },
          headers: conversationHeaders(),
          withCredentials: true,
          signal: scope.signal,
          sseMaxRetryAttempts: 5,
          onRequest: async (url, init) =>
            new Request(url, { ...init, credentials: "include" }),
          onSseEvent: (event) => {
            if (
              !scope.current() ||
              !event.data ||
              typeof event.data !== "object"
            )
              return
            const data = event.data as Record<string, unknown>
            if (event.event === "retrieval.started") setProgress("finding")
            if (event.event === "retrieval.complete") {
              const evidence = parseEvidence(data.evidence)
              if (evidence) setSources(evidence)
              const citations = parseCitationOutcomes(data.citation_outcomes)
              if (citations) setOutcomes(citations)
              setProgress("writing")
            }
            if (event.event === "generation.started") setProgress("writing")
            if (event.event === "verification.started") setProgress("checking")
            if (event.event === "translation.started")
              setProgress("translating")
            if (event.event === "answer.complete") {
              terminal = true
              // A malformed answer is not shown. The stored message that the
              // refetch below loads is shown in its place.
              const answer = parseAnswer(data.answer)
              if (answer) {
                setLiveAnswer(answer)
                if (
                  openSources &&
                  window.matchMedia("(min-width: 1280px)").matches
                )
                  setSelectedEvidence(answer.evidence[0] ?? null)
              }
              setRunId(null)
              setProgress(null)
              setPendingQuestion("")
              setStreamError(false)
              pendingKey.current = null
              queryClient.setQueryData<ConversationDetail>(
                ["conversation", conversationId],
                (current) =>
                  current ? { ...current, active_run_id: null } : current,
              )
              void queryClient.invalidateQueries({
                queryKey: ["conversation", conversationId],
              })
              void queryClient.invalidateQueries({
                queryKey: ["conversations"],
              })
            }
          },
          onSseError: () => {
            if (scope.current()) {
              setProgress("connectionLost")
              setStreamError(true)
            }
          },
        })
        for await (const _event of stream) {
          if (!scope.current() || terminal) break
        }
      } catch {
        if (scope.current()) setStreamError(true)
      } finally {
        if (scope.current() && !terminal) {
          setStreamError(true)
          setProgress("interrupted")
          void queryClient.invalidateQueries({
            queryKey: ["conversation", conversationId],
          })
        }
      }
    })()
    return () => scope.close()
  }, [
    activeRunId,
    beginRequest,
    openSources,
    queryClient,
    conversationId,
    streamAttempt,
    pendingKey,
    setProgress,
    setSources,
    setOutcomes,
    setLiveAnswer,
    setSelectedEvidence,
    setRunId,
    setPendingQuestion,
    setStreamError,
  ])
}
