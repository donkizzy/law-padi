import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useSearch } from "@tanstack/react-router"
import { AxiosError } from "axios"
import { useCallback, useEffect, useRef, useState } from "react"
import type { CitationOutcome, EvidenceItem, MessagePublic } from "@/client"
import { ConversationsService } from "@/client"
import { ChatComposer } from "@/components/LawPadi/ChatComposer"
import { ChatEvidencePanel } from "@/components/LawPadi/ChatEvidencePanel"
import {
  ErrorState,
  InlineAction,
  PromptSuggestion,
  SkeletonBlock,
} from "@/components/LawPadi/primitives"
import { conversationHeaders } from "@/hooks/useConversations"
import { useLegalSearch } from "@/hooks/useLegalCorpus"
import { bestContainingSource } from "@/lib/source-ranking"

const suggestions = [
  "Section 37",
  "What does the Constitution say about privacy?",
  "Section 33(2)(a)",
  "What facts matter if police search my phone?",
]

type ExplanationAnswer = {
  outcome: string
  blocks: Array<{
    text: string
    evidence_ids: string[]
    quotation?: string | null
  }>
  missing_facts: string[]
  citation_outcomes: CitationOutcome[]
  evidence: EvidenceItem[]
  notice?: string | null
}

function asAnswer(
  value: Record<string, unknown> | null,
): ExplanationAnswer | null {
  return value && typeof value.outcome === "string"
    ? (value as unknown as ExplanationAnswer)
    : null
}

function requestError(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail
    if (typeof detail === "string") return detail
  }
  return "The request could not be completed. Check your connection and try again."
}

function EvidenceCards({
  items,
  onSelect,
}: {
  items: EvidenceItem[]
  onSelect: (item: EvidenceItem) => void
}) {
  if (!items.length) return null
  return (
    <section aria-label="Source evidence" className="grid gap-3">
      <h3 className="text-sm font-semibold">Results</h3>
      {items.map((item) => (
        <button
          className="sq-md border border-border bg-card p-4 text-left hover:border-primary focus-visible:ring-2 focus-visible:ring-ring"
          key={item.evidence_id}
          onClick={() => onSelect(item)}
          type="button"
        >
          <span className="text-sm font-bold text-primary">
            {item.citation}
          </span>
          <span className="mt-2 block max-h-32 overflow-hidden whitespace-pre-wrap font-legal text-sm leading-6">
            {item.authoritative_text}
          </span>
          <span className="mt-2 block text-xs text-muted-foreground">
            {item.source_authority} · PDF page{" "}
            {item.source_page_start ?? "not recorded"}
          </span>
        </button>
      ))}
    </section>
  )
}

function LookupGaps({ outcomes }: { outcomes: CitationOutcome[] }) {
  const gaps = outcomes.filter((item) => item.status !== "resolved")
  if (!gaps.length) return null
  return (
    <section
      aria-label="Unresolved references"
      className="sq-md border border-amber-500/40 bg-amber-500/5 p-4"
    >
      <h3 className="text-sm font-semibold">References needing attention</h3>
      <ul className="mt-2 list-inside list-disc text-sm leading-6">
        {gaps.map((item, index) => (
          <li key={`${item.reference}:${index}`}>
            {item.reference}: {item.status}. {item.message}
          </li>
        ))}
      </ul>
    </section>
  )
}

function AnswerView({
  answer,
  onSelect,
}: {
  answer: ExplanationAnswer
  onSelect: (item: EvidenceItem) => void
}) {
  const bestSource = answer.citation_outcomes.length
    ? answer.evidence[0]
    : bestContainingSource(answer.evidence)
  return (
    <section aria-label="AI explanation" className="grid gap-4">
      {answer.blocks.length > 0 && (
        <div className="sq-lg border border-border bg-card p-5">
          <p className="mb-4 text-xs font-bold uppercase text-primary">
            AI explanation · {answer.outcome.replace(/_/g, " ")}
          </p>
          <div className="grid gap-5">
            {answer.blocks.map((block, index) => (
              <div key={index}>
                <p className="whitespace-pre-wrap text-sm leading-7">
                  {block.text}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {block.evidence_ids.map((id) => {
                    const item = answer.evidence.find(
                      (row) => row.evidence_id === id,
                    )
                    return item ? (
                      <button
                        className="sq-sm border border-primary/30 px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/5 focus-visible:ring-2 focus-visible:ring-ring"
                        key={id}
                        onClick={() => onSelect(item)}
                        type="button"
                      >
                        {item.citation}
                      </button>
                    ) : null
                  })}
                </div>
              </div>
            ))}
          </div>
          {answer.missing_facts.length > 0 && (
            <div className="mt-5 border-t border-border pt-4 text-sm">
              <p className="font-semibold">
                Facts that could change the explanation
              </p>
              <ul className="mt-2 list-inside list-disc">
                {answer.missing_facts.map((fact) => (
                  <li key={fact}>{fact}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      {answer.blocks.length === 0 && bestSource && (
        <div className="sq-lg border border-primary/30 bg-card p-5">
          <p className="mb-3 text-xs font-bold uppercase text-primary">
            Best published source wording · {bestSource.citation}
          </p>
          <p className="whitespace-pre-wrap font-legal text-sm leading-7">
            {bestSource.authoritative_text}
          </p>
          <InlineAction
            className="mt-4"
            onClick={() => onSelect(bestSource)}
            type="button"
          >
            View source details
          </InlineAction>
        </div>
      )}
      <LookupGaps outcomes={answer.citation_outcomes} />
      <EvidenceCards items={answer.evidence} onSelect={onSelect} />
    </section>
  )
}

function MessageView({
  message,
  onSelect,
}: {
  message: MessagePublic
  onSelect: (item: EvidenceItem) => void
}) {
  if (message.role === "user")
    return (
      <div className="ml-auto max-w-[90%] sq-lg bg-secondary px-4 py-3 text-sm leading-6">
        {message.content}
      </div>
    )
  const answer = asAnswer(message.answer_content)
  return answer ? (
    <AnswerView answer={answer} onSelect={onSelect} />
  ) : (
    <p className="text-sm text-muted-foreground">Explanation unavailable.</p>
  )
}

export function ChatHome() {
  const localPreview = import.meta.env.VITE_CHAT_PREVIEW === "true"
  const search = useSearch({ from: "/_layout/" })
  const navigate = useNavigate({ from: "/" })
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingQuestion, setPendingQuestion] = useState("")
  const [runId, setRunId] = useState<string | null>(null)
  const [progress, setProgress] = useState<string | null>(null)
  const [sources, setSources] = useState<EvidenceItem[]>([])
  const [outcomes, setOutcomes] = useState<CitationOutcome[]>([])
  const [liveAnswer, setLiveAnswer] = useState<ExplanationAnswer | null>(null)
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(
    null,
  )
  const [editingTitle, setEditingTitle] = useState(false)
  const [title, setTitle] = useState("")
  const [olderMessages, setOlderMessages] = useState<MessagePublic[]>([])
  const [olderBefore, setOlderBefore] = useState<string | null>(null)
  const [olderHasMore, setOlderHasMore] = useState<boolean | null>(null)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const autoHandled = useRef<string | null>(null)
  const pendingKey = useRef<{
    question: string
    conversationId: string
    selected?: string
    key: string
  } | null>(null)
  const submittedConversation = useRef<string | null>(null)

  const conversation = useQuery({
    queryKey: ["conversation", search.c],
    queryFn: async ({ signal }) =>
      (
        await ConversationsService.readConversation({
          path: { conversation_id: search.c! },
          headers: conversationHeaders(),
          withCredentials: true,
          signal,
        })
      ).data,
    enabled: Boolean(search.c),
    retry: false,
  })
  const previewQuery =
    pendingQuestion && (!search.c || conversation.data?.release_version)
      ? pendingQuestion
      : ""
  const preview = useLegalSearch(
    previewQuery,
    "auto",
    0,
    conversation.data?.release_version ?? search.release,
  )
  const activeRunId = conversation.data?.active_run_id ?? runId

  useEffect(() => {
    setOlderMessages([])
    setOlderBefore(null)
    setOlderHasMore(null)
    if (search.c && submittedConversation.current !== search.c) {
      setSources([])
      setOutcomes([])
      setLiveAnswer(null)
      setPendingQuestion("")
      setRunId(null)
      setProgress(null)
      setError(null)
    }
    submittedConversation.current = null
  }, [search.c])

  const loadOlder = async () => {
    if (!search.c || loadingOlder) return
    const before = olderBefore ?? conversation.data?.next_before
    if (!before || !(olderHasMore ?? conversation.data?.has_more_messages))
      return
    setLoadingOlder(true)
    try {
      const page = await ConversationsService.readConversation({
        path: { conversation_id: search.c },
        query: { before, limit: 50 },
        headers: conversationHeaders(),
        withCredentials: true,
      })
      setOlderMessages((current) => [...page.data.messages, ...current])
      setOlderBefore(page.data.next_before ?? null)
      setOlderHasMore(Boolean(page.data.has_more_messages))
    } catch (cause) {
      setError(requestError(cause))
    } finally {
      setLoadingOlder(false)
    }
  }

  const submit = useCallback(
    async (
      raw: string,
      releaseVersion?: string,
      selectedVersionId?: string,
    ) => {
      const question = raw.trim()
      if (!question || submitting) return
      setSubmitting(true)
      setPendingQuestion(question)
      setDraft("")
      setError(null)
      setSources([])
      setOutcomes([])
      setLiveAnswer(null)
      try {
        let conversationId = search.c
        if (!conversationId) {
          const created = await ConversationsService.createConversation({
            body: {
              release_version: releaseVersion ?? null,
              title: question.slice(0, 120),
            },
            headers: conversationHeaders(),
            withCredentials: true,
          })
          conversationId = created.data.id
        }
        const key =
          pendingKey.current?.question === question &&
          pendingKey.current.conversationId === conversationId &&
          pendingKey.current.selected === selectedVersionId
            ? pendingKey.current.key
            : crypto.randomUUID()
        pendingKey.current = {
          question,
          conversationId,
          selected: selectedVersionId,
          key,
        }
        const accepted = await ConversationsService.submitMessage({
          path: { conversation_id: conversationId },
          body: {
            question,
            idempotency_key: key,
            selected_provision_version_id: selectedVersionId ?? null,
          },
          headers: conversationHeaders(),
          withCredentials: true,
        })
        setRunId(accepted.data.run_id)
        setProgress("Finding published source wording…")
        submittedConversation.current = conversationId
        await navigate({
          to: "/",
          search: {
            c: conversationId,
            q: undefined,
            mode: "auto",
            release: undefined,
            selected: undefined,
          },
        })
        void queryClient.invalidateQueries({
          queryKey: ["conversation", conversationId],
        })
        void queryClient.invalidateQueries({ queryKey: ["conversations"] })
      } catch (cause) {
        setError(requestError(cause))
      } finally {
        setSubmitting(false)
      }
    },
    [navigate, queryClient, search.c, submitting],
  )

  useEffect(() => {
    if (!search.q) {
      autoHandled.current = null
      return
    }
    const key = `${search.q}:${search.release ?? ""}:${search.selected ?? ""}`
    if (autoHandled.current === key) return
    autoHandled.current = key
    void submit(search.q, search.release, search.selected)
  }, [search.q, search.release, search.selected, submit])

  useEffect(() => {
    if (!search.c || !activeRunId) return
    const controller = new AbortController()
    let closed = false
    void ConversationsService.conversationEvents({
      path: { conversation_id: search.c },
      query: { run_id: activeRunId },
      headers: conversationHeaders(),
      withCredentials: true,
      signal: controller.signal,
      sseMaxRetryAttempts: 5,
      onRequest: async (url, init) =>
        new Request(url, { ...init, credentials: "include" }),
      onSseEvent: (event) => {
        if (closed || !event.data || typeof event.data !== "object") return
        const data = event.data as Record<string, unknown>
        if (event.event === "retrieval.started")
          setProgress("Finding published source wording…")
        if (event.event === "retrieval.complete") {
          if (Array.isArray(data.evidence))
            setSources(data.evidence as EvidenceItem[])
          if (Array.isArray(data.citation_outcomes))
            setOutcomes(data.citation_outcomes as CitationOutcome[])
          setProgress("Preparing an explanation…")
        }
        if (event.event === "generation.started")
          setProgress("Preparing an explanation…")
        if (event.event === "verification.started")
          setProgress("Checking the explanation against the wording…")
        if (event.event === "answer.complete") {
          if (data.answer && typeof data.answer === "object")
            setLiveAnswer(data.answer as ExplanationAnswer)
          setRunId(null)
          setProgress(null)
          setPendingQuestion("")
          pendingKey.current = null
          void queryClient.invalidateQueries({
            queryKey: ["conversation", search.c],
          })
          void queryClient.invalidateQueries({ queryKey: ["conversations"] })
        }
      },
      onSseError: () => setProgress("Reconnecting to the explanation…"),
    }).then(async ({ stream }) => {
      for await (const _event of stream) {
        if (closed) break
      }
    })
    return () => {
      closed = true
      controller.abort()
    }
  }, [activeRunId, queryClient, search.c])

  const cancel = async () => {
    if (!search.c || !activeRunId) return
    try {
      await ConversationsService.cancelRun({
        path: { conversation_id: search.c, run_id: activeRunId },
        headers: conversationHeaders(),
        withCredentials: true,
      })
      setProgress("Cancelling explanation…")
    } catch (cause) {
      setError(requestError(cause))
    }
  }

  const rename = async () => {
    if (!search.c || !title.trim()) return
    try {
      await ConversationsService.renameConversation({
        path: { conversation_id: search.c },
        body: { title: title.trim() },
        headers: conversationHeaders(),
        withCredentials: true,
      })
      setEditingTitle(false)
      void queryClient.invalidateQueries({
        queryKey: ["conversation", search.c],
      })
      void queryClient.invalidateQueries({ queryKey: ["conversations"] })
    } catch (cause) {
      setError(requestError(cause))
    }
  }

  const remove = async () => {
    if (
      !search.c ||
      !window.confirm("Delete this conversation and its saved evidence?")
    )
      return
    try {
      await ConversationsService.deleteConversation({
        path: { conversation_id: search.c },
        headers: conversationHeaders(),
        withCredentials: true,
      })
      void queryClient.invalidateQueries({ queryKey: ["conversations"] })
      await navigate({
        to: "/",
        search: {
          c: undefined,
          q: undefined,
          mode: "auto",
          release: undefined,
        },
      })
    } catch (cause) {
      setError(requestError(cause))
    }
  }

  const latestAssistant = [...(conversation.data?.messages ?? [])]
    .reverse()
    .find((message) => message.role === "assistant")
  const latestUser = [...(conversation.data?.messages ?? [])]
    .reverse()
    .find((message) => message.role === "user")
  const visibleSources = sources.length
    ? sources
    : pendingQuestion
      ? (preview.data?.evidence ?? [])
      : []
  const visibleOutcomes = outcomes.length
    ? outcomes
    : pendingQuestion
      ? (preview.data?.citation_outcomes ?? [])
      : []
  const showPendingQuestion =
    pendingQuestion && latestUser?.content !== pendingQuestion
  const awaitingAnswer = Boolean(
    activeRunId &&
      (pendingQuestion ||
        (latestUser &&
          (!latestAssistant ||
            latestAssistant.created_at < latestUser.created_at))),
  )
  const showLiveAnswer =
    liveAnswer &&
    (!latestAssistant ||
      latestAssistant.created_at < (latestUser?.created_at ?? ""))
  const seenMessages = new Set<string>()
  const visibleMessages = [
    ...olderMessages,
    ...(conversation.data?.messages ?? []),
  ].filter((message) => {
    if (seenMessages.has(message.id)) return false
    seenMessages.add(message.id)
    return true
  })

  return (
    <div
      className={
        selectedEvidence ? "grid xl:grid-cols-[minmax(0,1fr)_380px]" : "grid"
      }
    >
      <section className="mx-auto flex min-h-[calc(100svh-4rem)] w-full max-w-4xl flex-col px-4 py-7 sm:px-8 lg:px-12">
        {/*{localPreview && (*/}
        {/*  <p*/}
        {/*    className="mb-5 sq-md border border-amber-500/40 bg-amber-500/5 p-3 text-sm"*/}
        {/*    role="status"*/}
        {/*  >*/}
        {/*    Local explanation preview. Answers appear only when source checks*/}
        {/*    pass; the published edition is historical.*/}
        {/*  </p>*/}
        {/*)}*/}
        {search.c ? (
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
            {editingTitle ? (
              <div className="flex gap-2">
                <input
                  aria-label="Conversation title"
                  className="sq-sm border border-input bg-card px-3 py-2 text-sm"
                  maxLength={255}
                  onChange={(event) => setTitle(event.target.value)}
                  value={title}
                />
                <InlineAction onClick={() => void rename()} type="button">
                  Save
                </InlineAction>
                <InlineAction
                  onClick={() => setEditingTitle(false)}
                  type="button"
                >
                  Cancel
                </InlineAction>
              </div>
            ) : (
              <div>
                <h1 className="font-legal text-2xl">
                  {conversation.data?.title || "Conversation"}
                </h1>
                <p className="mt-1 text-xs text-muted-foreground">
                  {conversation.data?.edition_label ?? "Published edition"}
                </p>
              </div>
            )}
            {/*<div className="flex gap-3 text-xs">*/}
            {/*  <InlineAction*/}
            {/*    onClick={() => {*/}
            {/*      setTitle(conversation.data?.title || "")*/}
            {/*      setEditingTitle(true)*/}
            {/*    }}*/}
            {/*    type="button"*/}
            {/*  >*/}
            {/*    Rename*/}
            {/*  </InlineAction>*/}
            {/*  <InlineAction onClick={() => void remove()} type="button">*/}
            {/*    Delete*/}
            {/*  </InlineAction>*/}
            {/*</div>*/}
          </div>
        ) : (
          <div className="mb-8">
            <p className="mb-4 text-xs font-bold uppercase text-primary">
              The law, made easy
            </p>
            <h1 className="font-legal text-[2.35rem] leading-[1.03] sm:text-[3.35rem]">
              Ask about Nigeria&apos;s Constitution.
            </h1>
            <p className="mt-4 text-sm leading-7 text-muted-foreground">
              Read the actual law text an explanation with
              links to its source.
            </p>
          </div>
        )}

        {conversation.isPending && search.c && <SkeletonBlock />}
        {conversation.isError && (
          <ErrorState title="Conversation unavailable">
            {requestError(conversation.error)}
          </ErrorState>
        )}
        <div className="grid flex-1 content-start gap-6">
          {(olderHasMore ?? conversation.data?.has_more_messages) && (
            <InlineAction
              disabled={loadingOlder}
              onClick={() => void loadOlder()}
              type="button"
            >
              {loadingOlder ? "Loading…" : "Load older messages"}
            </InlineAction>
          )}
          {visibleMessages.map((message) => (
            <MessageView
              key={message.id}
              message={message}
              onSelect={setSelectedEvidence}
            />
          ))}
          {showPendingQuestion && (
            <div className="ml-auto max-w-[90%] sq-lg bg-secondary px-4 py-3 text-sm leading-6">
              {pendingQuestion}
            </div>
          )}
          {awaitingAnswer && (
            <>
              <LookupGaps outcomes={visibleOutcomes} />
              <EvidenceCards
                items={visibleSources}
                onSelect={setSelectedEvidence}
              />
            </>
          )}
          {showLiveAnswer && (
            <AnswerView answer={liveAnswer} onSelect={setSelectedEvidence} />
          )}
          {progress && (
            <p role="status" className="text-sm text-muted-foreground">
              {progress}
            </p>
          )}
          {activeRunId && (
            <InlineAction onClick={() => void cancel()} type="button">
              Cancel explanation
            </InlineAction>
          )}
          {error && (
            <p role="alert" className="sq-md bg-destructive/10 p-4 text-sm">
              {error}
            </p>
          )}
        </div>

        <div className="sticky bottom-0 mt-8 bg-background/95 pb-5 pt-3 backdrop-blur">
          <ChatComposer
            value={draft}
            onChange={setDraft}
            onSubmit={() => void submit(draft)}
            purpose="explanation"
            loading={submitting}
            disabled={Boolean(activeRunId)}
            compact={Boolean(search.c)}
            contextLabel={conversation.data?.edition_label}
          />
          {!search.c && (
            <div className="mt-4 flex flex-wrap gap-2">
              {suggestions.map((prompt) => (
                <PromptSuggestion
                  key={prompt}
                  onClick={() => setDraft(prompt)}
                  type="button"
                >
                  {prompt}
                </PromptSuggestion>
              ))}
            </div>
          )}
          <p className="mt-3 text-xs text-muted-foreground">
            AI explanations can be wrong. Check the linked wording. Historical
            editions do not establish current consolidated law.
          </p>
        </div>
      </section>
      <ChatEvidencePanel
        evidence={selectedEvidence}
        onClose={() => setSelectedEvidence(null)}
        onExplain={(item) => {
          setSelectedEvidence(null)
          void submit(
            item.citation,
            item.release_version,
            item.provision_version_id,
          )
        }}
        explainDisabled={Boolean(activeRunId || submitting)}
      />
    </div>
  )
}
