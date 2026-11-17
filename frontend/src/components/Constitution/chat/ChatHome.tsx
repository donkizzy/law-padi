import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useSearch } from "@tanstack/react-router"
import { AxiosError } from "axios"
import { useCallback, useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { toast } from "sonner"
import {
  type CitationOutcome,
  type ConversationDetail,
  ConversationsService,
  type EvidenceItem,
  type Language,
  type MessagePublic,
} from "@/client"
import { AnswerBoundary } from "@/components/Constitution/AnswerBoundary"
import { AnswerLoading } from "@/components/Constitution/AnswerLoading"
import { ChatEvidencePanel } from "@/components/Constitution/ChatEvidencePanel"
import { ConversationComposer } from "@/components/Constitution/chat/ConversationComposer"
import {
  MessageList,
  useProgressLabel,
} from "@/components/Constitution/chat/MessageList"
import {
  type Progress,
  useAnswerStream,
} from "@/components/Constitution/chat/useAnswerStream"
import {
  ErrorState,
  InlineAction,
  SkeletonBlock,
  SquircleButton,
} from "@/components/Constitution/primitives"
import { useChatCapabilities } from "@/hooks/useChatCapabilities"
import { useChatDraft } from "@/hooks/useChatDraft"
import { useChatRequestScope } from "@/hooks/useChatRequestScope"
import { conversationHeaders } from "@/hooks/useConversations"
import { useLegalRelease } from "@/hooks/useLegalCorpus"
import { useWorkspacePreferences } from "@/hooks/useWorkspacePreferences"
import type { ExplanationAnswer } from "@/lib/answer"
import i18n from "@/lib/i18n"
import { releaseEditionName } from "@/lib/legal-provisions"
import { downloadResearch, readCompleteConversation } from "@/lib/research"

function requestError(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail
    if (error.response?.status === 503) return i18n.t("chat:errors.unavailable")
    if (error.response?.status === 429)
      return typeof detail === "string" &&
        detail.toLowerCase().includes("daily")
        ? i18n.t("chat:errors.dailyLimit")
        : i18n.t("chat:errors.busy")
    if (typeof detail === "string") return detail
  }
  return i18n.t("chat:errors.sendFailed")
}

export function ChatHome() {
  const { t } = useTranslation(["chat", "common"])
  const search = useSearch({ from: "/_layout/" })
  const navigate = useNavigate({ from: "/" })
  const queryClient = useQueryClient()
  const beginRequest = useChatRequestScope()
  const progressLabel = useProgressLabel()
  const capabilities = useChatCapabilities()
  const release = useLegalRelease()
  const { preferences } = useWorkspacePreferences()
  const { i18n: translator } = useTranslation()
  // A non-English interface asks for answers in that language; with English,
  // the question's own language decides.
  const interfaceLanguage = translator.resolvedLanguage ?? "en"
  const answerLanguage =
    interfaceLanguage !== "en" &&
    capabilities.data?.answer_languages?.some(
      (code) => code === interfaceLanguage,
    )
      ? (interfaceLanguage as Language)
      : null
  const [draft, setDraft] = useChatDraft(search.c ?? "new")
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const messageListRef = useRef<HTMLDivElement | null>(null)
  const nearBottom = useRef(true)
  const [showJump, setShowJump] = useState(false)
  const submittingRef = useRef(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingQuestion, setPendingQuestion] = useState("")
  const [runId, setRunId] = useState<string | null>(null)
  const [progress, setProgress] = useState<Progress | null>(null)
  const [queuePosition, setQueuePosition] = useState<number | null>(null)
  const [streamError, setStreamError] = useState(false)
  const [streamAttempt, setStreamAttempt] = useState(0)
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
  const [exporting, setExporting] = useState(false)
  const autoHandled = useRef<string | null>(null)
  const pendingKey = useRef<{
    question: string
    conversationId: string
    selected?: string
    key: string
  } | null>(null)

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
    retry: 1,
    refetchOnReconnect: true,
    refetchInterval: (query) =>
      query.state.data?.active_run_id || runId ? 2500 : false,
  })
  const activeRunId = conversation.data?.active_run_id ?? runId

  useEffect(() => {
    const data = conversation.data
    if (
      data &&
      !data.active_run_id &&
      data.messages[data.messages.length - 1]?.role === "assistant"
    ) {
      setRunId(null)
      setPendingQuestion("")
      setProgress(null)
      setStreamError(false)
      pendingKey.current = null
    }
  }, [conversation.data])

  useEffect(() => {
    const onScroll = () => {
      nearBottom.current =
        document.documentElement.scrollHeight -
          window.scrollY -
          window.innerHeight <
        200
      if (nearBottom.current) setShowJump(false)
    }
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])
  useEffect(() => {
    if (
      !search.c ||
      !(conversation.data?.messages.length || liveAnswer || pendingQuestion)
    )
      return
    if (preferences.followLatest && nearBottom.current) {
      const answers = messageListRef.current?.querySelectorAll<HTMLElement>(
        "[data-answer-start]",
      )
      const latestAnswer = answers?.item(answers.length - 1)
      if (latestAnswer && !pendingQuestion && !activeRunId)
        latestAnswer.scrollIntoView({ block: "start" })
      else bottomRef.current?.scrollIntoView({ block: "end" })
    } else setShowJump(true)
  }, [
    conversation.data?.messages.length,
    liveAnswer,
    pendingQuestion,
    activeRunId,
    preferences.followLatest,
    search.c,
  ])

  const loadOlder = async () => {
    if (!search.c || loadingOlder) return
    const before = olderBefore ?? conversation.data?.next_before
    if (!before || !(olderHasMore ?? conversation.data?.has_more_messages))
      return
    const scope = beginRequest()
    const scrollHeight = document.documentElement.scrollHeight
    const scrollTop = window.scrollY
    setLoadingOlder(true)
    try {
      const page = await ConversationsService.readConversation({
        path: { conversation_id: search.c },
        query: { before, limit: 50 },
        headers: conversationHeaders(),
        withCredentials: true,
        signal: scope.signal,
      })
      if (!scope.current()) return
      setOlderMessages((current) => [...page.data.messages, ...current])
      setOlderBefore(page.data.next_before ?? null)
      setOlderHasMore(Boolean(page.data.has_more_messages))
      requestAnimationFrame(() => {
        if (scope.current())
          window.scrollTo({
            top:
              scrollTop + document.documentElement.scrollHeight - scrollHeight,
          })
        scope.close()
      })
    } catch (cause) {
      if (scope.current()) setError(requestError(cause))
    } finally {
      if (scope.current()) setLoadingOlder(false)
    }
  }

  const submit = useCallback(
    async (
      raw: string,
      releaseVersion?: string,
      selectedVersionId?: string,
    ) => {
      const question = raw.trim()
      if (
        !question ||
        question.length > 2000 ||
        submittingRef.current ||
        activeRunId
      )
        return
      const scope = beginRequest()
      submittingRef.current = true
      setSubmitting(true)
      setPendingQuestion(question)
      setError(null)
      setSources([])
      setOutcomes([])
      setLiveAnswer(null)
      setStreamError(false)
      try {
        let conversationId = search.c ?? pendingKey.current?.conversationId
        if (!conversationId) {
          const created = await ConversationsService.createConversation({
            body: { release_version: releaseVersion ?? null, title: null },
            headers: conversationHeaders(),
            withCredentials: true,
            signal: scope.signal,
          })
          if (!scope.current()) return
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
            answer_language: answerLanguage,
          },
          headers: conversationHeaders(),
          withCredentials: true,
          signal: scope.signal,
        })
        if (!scope.current()) return
        setDraft("")
        setRunId(accepted.data.run_id)
        setProgress("finding")
        setSubmitting(false)
        submittingRef.current = false
        queryClient.setQueryData<ConversationDetail>(
          ["conversation", conversationId],
          (current) =>
            current
              ? {
                  ...current,
                  active_run_id: accepted.data.run_id,
                  messages: current.messages.some(
                    (message) => message.id === accepted.data.user_message_id,
                  )
                    ? current.messages
                    : [
                        ...current.messages,
                        {
                          id: accepted.data.user_message_id,
                          role: "user",
                          content: question,
                          created_at: new Date().toISOString(),
                          answer_status: null,
                          answer_content: null,
                          evidence_snapshot: null,
                        },
                      ],
                }
              : current,
        )
        void queryClient.invalidateQueries({ queryKey: ["conversations"] })
        await navigate({
          to: "/",
          search: {
            c: conversationId,
            q: undefined,
            mode: "auto",
            release: undefined,
            selected: undefined,
            intent: "ask",
            fresh: undefined,
          },
        })
        void queryClient.invalidateQueries({
          queryKey: ["conversation", conversationId],
        })
      } catch (cause) {
        if (scope.current()) {
          setError(requestError(cause))
          setDraft(question)
        }
      } finally {
        if (scope.current()) {
          setSubmitting(false)
          submittingRef.current = false
        }
        scope.close()
      }
    },
    [
      activeRunId,
      answerLanguage,
      beginRequest,
      navigate,
      queryClient,
      search.c,
      setDraft,
    ],
  )

  useEffect(() => {
    if (!search.q) return
    const key = `${search.q}:${search.release ?? ""}:${search.selected ?? ""}`
    let cancelled = false
    queueMicrotask(() => {
      if (cancelled || autoHandled.current === key) return
      autoHandled.current = key
      void submit(search.q!, search.release, search.selected)
    })
    return () => {
      cancelled = true
    }
  }, [search.q, search.release, search.selected, submit])

  useAnswerStream({
    conversationId: search.c,
    activeRunId,
    streamAttempt,
    openSources: preferences.openSources,
    beginRequest,
    pendingKey,
    setProgress,
    setQueuePosition,
    setSources,
    setOutcomes,
    setLiveAnswer,
    setSelectedEvidence,
    setRunId,
    setPendingQuestion,
    setStreamError,
  })

  const cancel = async () => {
    if (!search.c || !activeRunId) return
    const scope = beginRequest()
    try {
      await ConversationsService.cancelRun({
        path: { conversation_id: search.c, run_id: activeRunId },
        headers: conversationHeaders(),
        withCredentials: true,
        signal: scope.signal,
      })
      if (scope.current()) {
        setProgress("stopping")
        void conversation.refetch()
      }
    } catch (cause) {
      if (scope.current()) setError(requestError(cause))
    } finally {
      scope.close()
    }
  }

  const ask = (question: string) => void submit(question)

  const rename = async () => {
    if (!search.c || !title.trim()) return
    const scope = beginRequest()
    try {
      await ConversationsService.renameConversation({
        path: { conversation_id: search.c },
        body: { title: title.trim() },
        headers: conversationHeaders(),
        withCredentials: true,
        signal: scope.signal,
      })
      if (!scope.current()) return
      setEditingTitle(false)
      void queryClient.invalidateQueries({
        queryKey: ["conversation", search.c],
      })
      void queryClient.invalidateQueries({ queryKey: ["conversations"] })
    } catch (cause) {
      if (scope.current()) setError(requestError(cause))
    } finally {
      scope.close()
    }
  }

  const remove = async () => {
    if (!search.c || !window.confirm(t("conversation.confirmDelete"))) return
    const scope = beginRequest()
    try {
      await ConversationsService.deleteConversation({
        path: { conversation_id: search.c },
        headers: conversationHeaders(),
        withCredentials: true,
        signal: scope.signal,
      })
      if (!scope.current()) return
      void queryClient.invalidateQueries({ queryKey: ["conversations"] })
      await navigate({
        to: "/",
        search: {
          c: undefined,
          q: undefined,
          mode: "auto",
          release: undefined,
          selected: undefined,
          intent: "ask",
          fresh: crypto.randomUUID(),
        },
      })
    } catch (cause) {
      if (scope.current()) setError(requestError(cause))
    } finally {
      scope.close()
    }
  }

  const latestAssistant = [...(conversation.data?.messages ?? [])]
    .reverse()
    .find((message) => message.role === "assistant")
  const latestUser = [...(conversation.data?.messages ?? [])]
    .reverse()
    .find((message) => message.role === "user")
  const visibleSources = sources
  const visibleOutcomes = outcomes
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
        {search.c ? (
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
            {editingTitle ? (
              <div className="flex min-w-0 max-w-full flex-wrap gap-2">
                <input
                  aria-label={t("conversation.titleLabel")}
                  className="sq-sm min-w-0 flex-1 border border-input bg-card px-3 py-2 text-sm"
                  maxLength={255}
                  onChange={(event) => setTitle(event.target.value)}
                  value={title}
                />
                <InlineAction onClick={() => void rename()} type="button">
                  {t("common:actions.save")}
                </InlineAction>
                <InlineAction
                  onClick={() => setEditingTitle(false)}
                  type="button"
                >
                  {t("common:actions.cancel")}
                </InlineAction>
              </div>
            ) : (
              <div>
                <h1 className="font-display text-title-3">
                  {conversation.data?.title || t("common:history.untitled")}
                </h1>
                <p className="mt-1 text-label font-normal text-muted-foreground">
                  {releaseEditionName(
                    conversation.data?.edition_label ??
                      release.data?.edition_label,
                  )}
                </p>
              </div>
            )}
            <div className="flex gap-1">
              <SquircleButton
                disabled={exporting}
                size="sm"
                type="button"
                variant="ghost"
                onClick={async () => {
                  if (!search.c) return
                  const scope = beginRequest()
                  setExporting(true)
                  try {
                    const data = await readCompleteConversation(
                      search.c,
                      scope.signal,
                    )
                    if (scope.current())
                      downloadResearch("constitution-ng-conversation.json", {
                        format_version: 1,
                        exported_at: new Date().toISOString(),
                        conversation: data,
                        notice:
                          "Preserve source edition details when sharing. Explanations are not legal advice.",
                      })
                  } catch {
                    if (scope.current())
                      toast.error(t("conversation.exportFailed"))
                  } finally {
                    if (scope.current()) setExporting(false)
                    scope.close()
                  }
                }}
              >
                {exporting
                  ? t("conversation.exporting")
                  : t("conversation.export")}
              </SquircleButton>
              <SquircleButton
                onClick={() => {
                  setTitle(conversation.data?.title || "")
                  setEditingTitle(true)
                }}
                size="sm"
                type="button"
                variant="ghost"
              >
                {t("conversation.rename")}
              </SquircleButton>
              <SquircleButton
                onClick={() => void remove()}
                size="sm"
                type="button"
                variant="ghost"
              >
                {t("conversation.delete")}
              </SquircleButton>
            </div>
          </div>
        ) : (
          <div className="mb-8">
            <p className="mb-4 text-overline uppercase text-primary">
              {t("home.kicker")}
            </p>
            <h1 className="font-display text-title-1 sm:text-display">
              {t("home.title")}
            </h1>
            <p className="mt-4 max-w-xl text-body-lg text-muted-foreground">
              {t("home.intro")}
            </p>
          </div>
        )}

        {conversation.isPending && search.c && <SkeletonBlock />}
        {conversation.isError && (
          <ErrorState
            title={t("conversation.unavailable")}
            action={
              <InlineAction
                type="button"
                onClick={() => void conversation.refetch()}
              >
                {t("common:actions.tryAgain")}
              </InlineAction>
            }
          >
            {requestError(conversation.error)}
          </ErrorState>
        )}
        <MessageList
          listRef={messageListRef}
          hasOlder={Boolean(
            olderHasMore ?? conversation.data?.has_more_messages,
          )}
          loadingOlder={loadingOlder}
          onLoadOlder={() => void loadOlder()}
          messages={visibleMessages}
          conversationId={search.c}
          latestAssistantId={latestAssistant?.id}
          activeRunId={activeRunId}
          onAsk={ask}
          onSelect={setSelectedEvidence}
          pendingQuestion={pendingQuestion}
          showPendingQuestion={Boolean(showPendingQuestion)}
          awaitingAnswer={awaitingAnswer}
          liveAnswer={liveAnswer}
          showLiveAnswer={Boolean(showLiveAnswer)}
          outcomes={visibleOutcomes}
          progress={progress}
          queuePosition={queuePosition}
          sources={visibleSources}
        >
          {progress && !awaitingAnswer && (
            <AnswerLoading
              progress={progress}
              label={progressLabel(progress, queuePosition)}
            />
          )}
          {activeRunId && (
            <SquircleButton
              className="w-fit"
              onClick={() => void cancel()}
              size="sm"
              type="button"
              variant="outline"
            >
              {t("conversation.stop")}
            </SquircleButton>
          )}
          {streamError && (
            <div
              className="sq-md border border-border bg-secondary p-4 text-body"
              role="status"
            >
              {t("stream.saved")}
              <div className="mt-2 flex flex-wrap gap-2">
                <InlineAction
                  type="button"
                  onClick={() => {
                    setStreamError(false)
                    setStreamAttempt((value) => value + 1)
                  }}
                >
                  {t("stream.reconnect")}
                </InlineAction>
                <InlineAction
                  type="button"
                  onClick={() => void conversation.refetch()}
                >
                  {t("stream.checkStatus")}
                </InlineAction>
              </div>
            </div>
          )}
          {error && (
            <div role="alert" className="sq-md bg-destructive/10 p-4 text-body">
              {error}
              <div className="mt-2 flex flex-wrap gap-2">
                {pendingKey.current && (
                  <InlineAction
                    type="button"
                    disabled={submitting || Boolean(activeRunId)}
                    onClick={() =>
                      void submit(
                        pendingKey.current!.question,
                        search.release,
                        pendingKey.current!.selected,
                      )
                    }
                  >
                    {t("errors.retry")}
                  </InlineAction>
                )}
                <InlineAction
                  type="button"
                  onClick={() => {
                    setError(null)
                    inputRef.current?.focus()
                  }}
                >
                  {t("errors.edit")}
                </InlineAction>
                <InlineAction
                  type="button"
                  onClick={() =>
                    void navigate({
                      to: "/",
                      search: {
                        intent: "find",
                        q: pendingQuestion || draft,
                        mode: "auto",
                      },
                    })
                  }
                >
                  {t("errors.findSections")}
                </InlineAction>
              </div>
            </div>
          )}
        </MessageList>

        <ConversationComposer
          bottomRef={bottomRef}
          showJump={showJump}
          onJumpToLatest={() => {
            nearBottom.current = true
            setShowJump(false)
            bottomRef.current?.scrollIntoView({
              block: "end",
              behavior: window.matchMedia("(prefers-reduced-motion: reduce)")
                .matches
                ? "auto"
                : "smooth",
            })
          }}
          explanationsEnabled={capabilities.data?.explanations_enabled}
          inputRef={inputRef}
          autoFocus={!search.c && Boolean(search.fresh)}
          draft={draft}
          onDraftChange={setDraft}
          onSubmit={() => void submit(draft)}
          submitting={submitting}
          disabled={
            Boolean(activeRunId) || !capabilities.data?.explanations_enabled
          }
          compact={Boolean(search.c)}
          contextLabel={releaseEditionName(
            conversation.data?.edition_label ?? release.data?.edition_label,
          )}
          showSuggestions={!search.c}
        />
      </section>
      <AnswerBoundary resetKey={selectedEvidence}>
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
          explainDisabled={
            Boolean(activeRunId || submitting) ||
            !capabilities.data?.explanations_enabled
          }
        />
      </AnswerBoundary>
    </div>
  )
}
