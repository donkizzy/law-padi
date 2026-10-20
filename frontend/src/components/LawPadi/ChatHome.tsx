import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useSearch } from "@tanstack/react-router"
import { AxiosError } from "axios"
import { useCallback, useEffect, useRef, useState } from "react"
import { FiArrowDown } from "react-icons/fi"
import { toast } from "sonner"
import type {
  CitationOutcome,
  ConversationDetail,
  EvidenceItem,
  MessagePublic,
} from "@/client"
import { ConversationsService } from "@/client"
import { ChatComposer } from "@/components/LawPadi/ChatComposer"
import { ChatEvidencePanel } from "@/components/LawPadi/ChatEvidencePanel"
import {
  ErrorState,
  InlineAction,
  PromptSuggestion,
  SkeletonBlock,
  SquircleButton,
} from "@/components/LawPadi/primitives"
import { useChatCapabilities } from "@/hooks/useChatCapabilities"
import { useChatDraft } from "@/hooks/useChatDraft"
import { useChatRequestScope } from "@/hooks/useChatRequestScope"
import { conversationHeaders } from "@/hooks/useConversations"
import { useLegalRelease } from "@/hooks/useLegalCorpus"
import { useSavedProvisions } from "@/hooks/useSavedProvisions"
import { useWorkspacePreferences } from "@/hooks/useWorkspacePreferences"
import {
  editionNote,
  readableText,
  releaseEditionName,
  shortCitation,
} from "@/lib/legal-provisions"
import {
  downloadResearch,
  evidenceCopy,
  readCompleteConversation,
} from "@/lib/research"
import { bestContainingSource } from "@/lib/source-ranking"
import { cn } from "@/lib/utils"
import { AnswerFeedback } from "./AnswerFeedback"
import { EditionNotice } from "./EditionNotice"

const suggestions = [
  "Can police search my phone?",
  "How long can police hold me before court?",
  "Who can run for president?",
  "What does Section 37 say?",
]

type ExplanationAnswer = {
  outcome: string
  blocks: Array<{
    text: string
    evidence_ids: string[]
    quotation?: string | null
  }>
  missing_facts: string[]
  follow_up_questions?: string[]
  citation_outcomes: CitationOutcome[]
  evidence: EvidenceItem[]
  related_laws?: string[]
  notice?: string | null
}

// Fallbacks for older answers that have no server-provided notice.
const outcomeMessages: Record<string, string> = {
  clarification_required:
    "That question covers a lot at once. Try asking about one law, section or issue.",
  validation_failed:
    "We couldn't confirm that the explanation matches the published provisions, so here are the sections themselves.",
  provider_failure:
    "Explanations aren't available right now. Here are the relevant published sections.",
  budget_exhausted:
    "We've reached today's limit for explanations. Here are the relevant published sections.",
  capacity_exhausted:
    "A lot of people are asking questions right now. Here is the relevant text; try again in a minute.",
  cancelled: "You stopped this answer.",
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
    if (error.response?.status === 503)
      return "Explanations are temporarily unavailable. Your question is still here; try again or find the relevant sections."
    if (error.response?.status === 429)
      return typeof detail === "string" &&
        detail.toLowerCase().includes("daily")
        ? "You've reached today's explanation allowance. It resets at midnight in Lagos. You can still find and read sections."
        : "Explanations are busy right now. Try again in a minute, or find the relevant sections."
    if (typeof detail === "string") return detail
  }
  return "Something went wrong sending your question. Check your connection and try again."
}

function AnswerActions({ answer }: { answer: ExplanationAnswer }) {
  const { isSaved, toggle } = useSavedProvisions()
  const copy = async () => {
    try {
      const explanation = answer.blocks
        .map(
          (block) =>
            `${block.text}\n${block.evidence_ids
              .map(
                (id) =>
                  answer.evidence.find((item) => item.evidence_id === id)
                    ?.citation,
              )
              .filter(Boolean)
              .join("; ")}`,
        )
        .join("\n\n")
      const facts = answer.missing_facts.length
        ? `\n\nThe answer may depend on:\n${answer.missing_facts.join("\n")}`
        : ""
      const laws = answer.related_laws?.length
        ? `\n\nOther laws also apply:\n${answer.related_laws.join("\n")}`
        : ""
      await navigator.clipboard.writeText(
        `${explanation || statusMessage(answer)}${facts}${laws}\n\nSources:\n${answer.evidence.map(evidenceCopy).join("\n\n")}\n\nThis explanation is not legal advice.`,
      )
      toast.success("Answer and citations copied")
    } catch {
      toast.error("Couldn't copy. Please try again.")
    }
  }
  const save = () => {
    try {
      const items = splitSources(answer).cited
      const sources = items.length ? items : answer.evidence.slice(0, 4)
      for (const item of sources)
        if (!isSaved(item.canonical_path, item.release_version))
          toggle(item.canonical_path, item.release_version)
      toast.success("Sources saved")
    } catch {
      toast.error("Couldn't save sources on this browser.")
    }
  }
  return (
    <fieldset className="flex flex-wrap gap-2" aria-label="Answer actions">
      <InlineAction type="button" onClick={() => void copy()}>
        Copy answer with citations
      </InlineAction>
      {answer.evidence.length > 0 && (
        <InlineAction type="button" onClick={save}>
          Save sources
        </InlineAction>
      )}
      <InlineAction
        type="button"
        onClick={() =>
          downloadResearch("constitution-ng-answer.json", {
            format_version: 1,
            exported_at: new Date().toISOString(),
            answer,
            sources: answer.evidence.map(evidenceCopy),
            notice: "Explanations are not legal advice.",
          })
        }
      >
        Export answer
      </InlineAction>
    </fieldset>
  )
}

function statusMessage(answer: ExplanationAnswer) {
  if (answer.notice) return answer.notice
  const gap = answer.citation_outcomes.find((row) => row.status !== "resolved")
  if (answer.outcome === "insufficient_evidence") {
    if (gap?.message) return gap.message
    return answer.evidence.length
      ? "The published provisions don't seem to answer this directly. Here are the closest sections we found."
      : "We couldn't find a published section that answers this. Try rephrasing, or name a law and section."
  }
  return (
    outcomeMessages[answer.outcome] ??
    "We couldn't finish this answer. Here are the relevant published sections."
  )
}

function answerEditionNotice(answer: ExplanationAnswer) {
  if (answer.blocks.length && answer.notice) return answer.notice
  const instruments = new Map<string, EvidenceItem>()
  for (const item of answer.evidence) {
    if (item.legal_status !== "historical") continue
    const slug = item.instrument_slug || item.canonical_path.split(".")[0]
    if (!instruments.has(slug)) instruments.set(slug, item)
  }
  return [...instruments.entries()]
    .map(([slug, item]) =>
      slug === "constitution-1999"
        ? editionNote(item.edition_label)
        : `${item.instrument_short_title || item.instrument_title || slug}: As enacted, may have been amended.`,
    )
    .join("\n\n")
}

/** Drop sources whose text sits inside another listed source (35(3) in 35). */
function withoutContained(items: EvidenceItem[]) {
  return items.filter(
    (item) =>
      !items.some(
        (other) =>
          other !== item &&
          item.canonical_path.startsWith(`${other.canonical_path}.`),
      ),
  )
}

function splitSources(answer: ExplanationAnswer) {
  const ids = new Set(answer.blocks.flatMap((block) => block.evidence_ids))
  const order = [...ids]
  const cited = withoutContained(
    answer.evidence
      .filter((item) => ids.has(item.evidence_id))
      .sort(
        (a, b) => order.indexOf(a.evidence_id) - order.indexOf(b.evidence_id),
      ),
  )
  const others = withoutContained(
    answer.evidence.filter(
      (item) =>
        !ids.has(item.evidence_id) &&
        !cited.some(
          (source) =>
            item.canonical_path === source.canonical_path ||
            item.canonical_path.startsWith(`${source.canonical_path}.`),
        ),
    ),
  )
  return { cited, others }
}

function newCitations(blocks: ExplanationAnswer["blocks"], index: number) {
  const previous = new Set(blocks[index - 1]?.evidence_ids ?? [])
  return blocks[index].evidence_ids.filter((id) => !previous.has(id))
}

/** Paragraphs, with lines starting "- " grouped into a list. */
function BlockText({ text, lead }: { text: string; lead?: boolean }) {
  const groups: Array<{ list: boolean; lines: string[] }> = []
  for (const raw of text.split("\n")) {
    const line = raw.trim()
    if (!line) continue
    const list = /^[-•]\s+/.test(line)
    const value = line.replace(/^[-•]\s+/, "")
    const last = groups[groups.length - 1]
    if (last && last.list === list && list) last.lines.push(value)
    else groups.push({ list, lines: [value] })
  }
  const size = lead ? "text-body-lg text-foreground" : "text-body"
  return (
    <div className="grid gap-2">
      {groups.map((group, index) =>
        group.list ? (
          <ul
            className={cn("ml-5 grid list-disc gap-1", size)}
            key={`${index}:list`}
          >
            {group.lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        ) : (
          <p className={size} key={`${index}:text`}>
            {group.lines.join(" ")}
          </p>
        ),
      )}
    </div>
  )
}

function SourceChip({
  item,
  onSelect,
}: {
  item: EvidenceItem
  onSelect: (item: EvidenceItem) => void
}) {
  return (
    <button
      className="sq-sm min-h-11 border border-primary/25 px-3 py-2 text-label text-primary hover:bg-primary/5 focus-visible:ring-2 focus-visible:ring-ring"
      onClick={() => onSelect(item)}
      title={item.title ?? undefined}
      aria-label={item.citation}
      type="button"
    >
      {shortCitation(item)}
    </button>
  )
}

function SourceCard({
  item,
  onSelect,
}: {
  item: EvidenceItem
  onSelect: (item: EvidenceItem) => void
}) {
  return (
    <button
      aria-label={`Open ${item.citation}${item.title ? `: ${item.title}` : " source"}`}
      className="sq-md grid gap-1 border border-border bg-card p-4 text-left hover:border-primary focus-visible:ring-2 focus-visible:ring-ring"
      onClick={() => onSelect(item)}
      type="button"
    >
      <span className="text-label text-primary">{item.citation}</span>
      {item.title && (
        <span className="text-body font-semibold">{item.title}</span>
      )}
      <span className="hidden font-legal text-statute-sm text-muted-foreground sm:line-clamp-2">
        {item.authoritative_text.replace(/\s+/g, " ")}
      </span>
    </button>
  )
}

function SourceList({
  title,
  items,
  onSelect,
}: {
  title: string
  items: EvidenceItem[]
  onSelect: (item: EvidenceItem) => void
}) {
  if (!items.length) return null
  return (
    <section aria-label={title} className="grid gap-3">
      <h3 className="text-overline uppercase text-muted-foreground">{title}</h3>
      <div className="grid gap-3">
        {items.map((item) => (
          <SourceCard item={item} key={item.evidence_id} onSelect={onSelect} />
        ))}
      </div>
    </section>
  )
}

function LookupGaps({ outcomes }: { outcomes: CitationOutcome[] }) {
  const gaps = outcomes.filter((item) => item.status !== "resolved")
  if (!gaps.length) return null
  return (
    <section
      aria-label="Sections we couldn't find"
      className="sq-md border border-amber-500/40 bg-amber-500/5 p-4"
    >
      <h3 className="text-body font-semibold">We couldn't find everything</h3>
      <ul className="mt-2 list-inside list-disc text-body">
        {gaps.map((item, index) => (
          <li key={`${item.reference}:${index}`}>
            {item.reference}: {item.message}
          </li>
        ))}
      </ul>
    </section>
  )
}

/** Curated names of other laws on the subject; not part of the answer. */
function RelatedLaws({
  laws,
  className,
}: {
  laws?: string[]
  className?: string
}) {
  if (!laws?.length) return null
  return (
    <section aria-label="Other laws also apply" className={className}>
      <h3 className="text-body font-semibold">Other laws also apply</h3>
      <p className="mt-1 text-body text-muted-foreground">
        These Nigerian laws also cover this. They aren't included here yet, so
        check them or ask a lawyer before relying on this answer.
      </p>
      <ul className="mt-2 ml-5 grid list-disc gap-1 text-body">
        {laws.map((law) => (
          <li key={law}>{law}</li>
        ))}
      </ul>
    </section>
  )
}

function FollowUps({
  questions,
  onAsk,
}: {
  questions: string[]
  onAsk: (question: string) => void
}) {
  if (!questions.length) return null
  return (
    <section aria-label="Suggested questions" className="grid gap-3">
      <h3 className="text-overline uppercase text-muted-foreground">
        You might also ask
      </h3>
      <div className="flex flex-wrap gap-2">
        {questions.map((question) => (
          <PromptSuggestion key={question} onClick={() => onAsk(question)}>
            {question}
          </PromptSuggestion>
        ))}
      </div>
    </section>
  )
}

function AnswerView({
  answer,
  onSelect,
  onAsk,
}: {
  answer: ExplanationAnswer
  onSelect: (item: EvidenceItem) => void
  onAsk?: (question: string) => void
}) {
  const byId = new Map(answer.evidence.map((item) => [item.evidence_id, item]))
  const historical = answer.evidence.find(
    (item) => item.legal_status === "historical",
  )
  if (!answer.blocks.length) {
    const bestSource = answer.citation_outcomes.length
      ? answer.evidence[0]
      : bestContainingSource(answer.evidence)
    const others = withoutContained(
      answer.evidence.filter(
        (item) =>
          item !== bestSource &&
          !item.canonical_path.startsWith(`${bestSource?.canonical_path}.`),
      ),
    )
    return (
      <section aria-label="Answer" className="grid gap-5">
        <p className="sq-md bg-secondary p-4 text-body" role="status">
          {statusMessage(answer)}
        </p>
        <RelatedLaws laws={answer.related_laws} />
        <EditionNotice
          label={historical?.edition_label}
          historical={Boolean(historical)}
          notice={answerEditionNotice(answer)}
        />
        <AnswerActions answer={answer} />
        <LookupGaps outcomes={answer.citation_outcomes} />
        {bestSource && (
          <div className="sq-lg border border-border bg-card p-5">
            <p className="text-label text-primary">{bestSource.citation}</p>
            {bestSource.title && (
              <h3 className="mt-1 font-display text-title-3">
                {bestSource.title}
              </h3>
            )}
            <p className="mt-3 whitespace-pre-wrap font-legal text-statute-sm">
              {readableText(bestSource.authoritative_text)}
            </p>
            <InlineAction
              className="mt-4"
              onClick={() => onSelect(bestSource)}
              type="button"
            >
              More about this section
            </InlineAction>
          </div>
        )}
        <SourceList
          items={others.slice(0, 4)}
          onSelect={onSelect}
          title="Other sections that may help"
        />
        {onAsk && (
          <FollowUps
            onAsk={onAsk}
            questions={answer.follow_up_questions ?? []}
          />
        )}
      </section>
    )
  }
  const { cited, others } = splitSources(answer)
  return (
    <section aria-label="Answer" className="grid gap-5">
      <div className="sq-lg border border-border bg-card p-5 sm:p-6">
        <div className="grid gap-5">
          {answer.blocks.map((block, index) => (
            <div key={`${index}:${block.text.slice(0, 24)}`}>
              <BlockText lead={index === 0} text={block.text} />
              <div className="mt-2 flex flex-wrap gap-2 empty:hidden">
                {/* A section already shown on the block above isn't repeated. */}
                {newCitations(answer.blocks, index).map((id) => {
                  const item = byId.get(id)
                  return item ? (
                    <SourceChip item={item} key={id} onSelect={onSelect} />
                  ) : null
                })}
              </div>
            </div>
          ))}
        </div>
        {answer.missing_facts.length > 0 && (
          <div className="mt-6 border-t border-border pt-4">
            <h3 className="text-body font-semibold">
              The answer may depend on
            </h3>
            <ul className="mt-2 ml-5 grid list-disc gap-1 text-body">
              {answer.missing_facts.map((fact) => (
                <li key={fact}>{fact}</li>
              ))}
            </ul>
          </div>
        )}
        <RelatedLaws
          className="mt-6 border-t border-border pt-4"
          laws={answer.related_laws}
        />
        <EditionNotice
          label={historical?.edition_label}
          historical={Boolean(historical)}
          notice={answerEditionNotice(answer)}
          className="mt-5 border-t border-border pt-4"
        />
      </div>
      <LookupGaps outcomes={answer.citation_outcomes} />
      <AnswerActions answer={answer} />
      <SourceList items={cited} onSelect={onSelect} title="Sections used" />
      {others.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-body text-muted-foreground hover:text-foreground">
            {others.length === 1
              ? "1 other section came up"
              : `${others.length} other sections came up`}
          </summary>
          <div className="mt-3">
            <SourceList
              items={others}
              onSelect={onSelect}
              title="Also related"
            />
          </div>
        </details>
      )}
      {onAsk && (
        <FollowUps onAsk={onAsk} questions={answer.follow_up_questions ?? []} />
      )}
    </section>
  )
}

function PendingAnswer({
  progress,
  sources,
  outcomes,
}: {
  progress: string | null
  sources: EvidenceItem[]
  outcomes: CitationOutcome[]
}) {
  const reading = withoutContained(sources).slice(0, 4)
  return (
    <section aria-label="Answer in progress" className="grid gap-4">
      <LookupGaps outcomes={outcomes} />
      <div className="sq-lg grid gap-3 border border-border bg-card p-5">
        <p className="text-body text-muted-foreground" role="status">
          {progress ?? "Finding the relevant sections…"}
        </p>
        {reading.length > 0 && (
          <p className="text-label font-normal text-muted-foreground">
            Reading{" "}
            {reading
              .map((item) =>
                item.title ? `${item.citation} (${item.title})` : item.citation,
              )
              .join(", ")}
          </p>
        )}
        <div aria-hidden className="grid gap-2">
          <div className="sq-xs h-3 w-11/12 animate-pulse bg-muted" />
          <div className="sq-xs h-3 w-9/12 animate-pulse bg-muted" />
          <div className="sq-xs h-3 w-10/12 animate-pulse bg-muted" />
        </div>
      </div>
    </section>
  )
}

function MessageView({
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
  if (message.role === "user")
    return (
      <div className="ml-auto max-w-[90%] sq-lg bg-secondary px-4 py-3 text-body">
        {message.content}
      </div>
    )
  const answer = asAnswer(message.answer_content)
  return answer ? (
    <div data-answer-start="" className="scroll-mt-24">
      <AnswerView answer={answer} onAsk={onAsk} onSelect={onSelect} />
      {conversationId && (
        <AnswerFeedback message={message} conversationId={conversationId} />
      )}
    </div>
  ) : (
    <p className="text-body text-muted-foreground">
      This answer couldn't be loaded.
    </p>
  )
}

export function ChatHome() {
  const search = useSearch({ from: "/_layout/" })
  const navigate = useNavigate({ from: "/" })
  const queryClient = useQueryClient()
  const beginRequest = useChatRequestScope()
  const capabilities = useChatCapabilities()
  const release = useLegalRelease()
  const { preferences } = useWorkspacePreferences()
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
  const [progress, setProgress] = useState<string | null>(null)
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
          },
          headers: conversationHeaders(),
          withCredentials: true,
          signal: scope.signal,
        })
        if (!scope.current()) return
        setDraft("")
        setRunId(accepted.data.run_id)
        setProgress("Finding the relevant sections…")
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
    [activeRunId, beginRequest, navigate, queryClient, search.c, setDraft],
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

  useEffect(() => {
    if (!search.c || !activeRunId) return
    const scope = beginRequest()
    let terminal = false
    if (streamAttempt > 0) setProgress("Reconnecting to your saved question…")
    void (async () => {
      try {
        const { stream } = await ConversationsService.conversationEvents({
          path: { conversation_id: search.c! },
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
            if (event.event === "retrieval.started")
              setProgress("Finding the relevant sections…")
            if (event.event === "retrieval.complete") {
              if (Array.isArray(data.evidence))
                setSources(data.evidence as EvidenceItem[])
              if (Array.isArray(data.citation_outcomes))
                setOutcomes(data.citation_outcomes as CitationOutcome[])
              setProgress("Writing a plain-English answer…")
            }
            if (event.event === "generation.started")
              setProgress("Writing a plain-English answer…")
            if (event.event === "verification.started")
              setProgress("Double-checking the answer against its sources…")
            if (event.event === "answer.complete") {
              terminal = true
              if (data.answer && typeof data.answer === "object") {
                const answer = data.answer as ExplanationAnswer
                setLiveAnswer(answer)
                if (
                  preferences.openSources &&
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
                ["conversation", search.c],
                (current) =>
                  current ? { ...current, active_run_id: null } : current,
              )
              void queryClient.invalidateQueries({
                queryKey: ["conversation", search.c],
              })
              void queryClient.invalidateQueries({
                queryKey: ["conversations"],
              })
            }
          },
          onSseError: () => {
            if (scope.current()) {
              setProgress("Connection lost. Reconnecting…")
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
          setProgress(
            "The connection was interrupted. We're checking whether your answer finished.",
          )
          void queryClient.invalidateQueries({
            queryKey: ["conversation", search.c],
          })
        }
      }
    })()
    return () => scope.close()
  }, [
    activeRunId,
    beginRequest,
    preferences.openSources,
    queryClient,
    search.c,
    streamAttempt,
  ])

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
        setProgress("Stopping…")
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
    if (
      !search.c ||
      !window.confirm("Delete this conversation? This can't be undone.")
    )
      return
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
                  aria-label="Conversation title"
                  className="sq-sm min-w-0 flex-1 border border-input bg-card px-3 py-2 text-sm"
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
                <h1 className="font-display text-title-3">
                  {conversation.data?.title || "Conversation"}
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
                      toast.error(
                        "Conversation could not be fully exported. Try again.",
                      )
                  } finally {
                    if (scope.current()) setExporting(false)
                    scope.close()
                  }
                }}
              >
                {exporting ? "Exporting…" : "Export chat"}
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
                Rename
              </SquircleButton>
              <SquircleButton
                onClick={() => void remove()}
                size="sm"
                type="button"
                variant="ghost"
              >
                Delete
              </SquircleButton>
            </div>
          </div>
        ) : (
          <div className="mb-8">
            <p className="mb-4 text-overline uppercase text-primary">
              The law, made easy
            </p>
            <h1 className="font-display text-title-1 sm:text-display">
              Ask about Nigeria&apos;s laws.
            </h1>
            <p className="mt-4 max-w-xl text-body-lg text-muted-foreground">
              Ask in your own words. You&apos;ll get a plain-English answer and
              the exact sections it comes from.
            </p>
          </div>
        )}

        {conversation.isPending && search.c && <SkeletonBlock />}
        {conversation.isError && (
          <ErrorState title="Conversation unavailable">
            {requestError(conversation.error)}
            <InlineAction
              type="button"
              onClick={() => void conversation.refetch()}
            >
              Try again
            </InlineAction>
          </ErrorState>
        )}
        <div ref={messageListRef} className="grid flex-1 content-start gap-6">
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
              conversationId={search.c}
              onAsk={
                message.id === latestAssistant?.id && !activeRunId
                  ? ask
                  : undefined
              }
              onSelect={setSelectedEvidence}
            />
          ))}
          {showPendingQuestion && (
            <div className="ml-auto max-w-[90%] sq-lg bg-secondary px-4 py-3 text-sm leading-6">
              {pendingQuestion}
            </div>
          )}
          {awaitingAnswer && !showLiveAnswer && (
            <PendingAnswer
              outcomes={visibleOutcomes}
              progress={progress}
              sources={visibleSources}
            />
          )}
          {showLiveAnswer && (
            <div data-answer-start="" className="scroll-mt-24">
              <AnswerView
                answer={liveAnswer}
                onAsk={activeRunId ? undefined : ask}
                onSelect={setSelectedEvidence}
              />
            </div>
          )}
          {progress && !awaitingAnswer && (
            <p role="status" className="text-body text-muted-foreground">
              {progress}
            </p>
          )}
          {activeRunId && (
            <SquircleButton
              className="w-fit"
              onClick={() => void cancel()}
              size="sm"
              type="button"
              variant="outline"
            >
              Stop answering
            </SquircleButton>
          )}
          {streamError && (
            <div
              className="sq-md border border-border bg-secondary p-4 text-body"
              role="status"
            >
              Your question is saved. Reconnect or check its status to continue.
              <div className="mt-2 flex flex-wrap gap-2">
                <InlineAction
                  type="button"
                  onClick={() => {
                    setStreamError(false)
                    setStreamAttempt((value) => value + 1)
                  }}
                >
                  Reconnect
                </InlineAction>
                <InlineAction
                  type="button"
                  onClick={() => void conversation.refetch()}
                >
                  Check answer status
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
                    Retry question
                  </InlineAction>
                )}
                <InlineAction
                  type="button"
                  onClick={() => {
                    setError(null)
                    inputRef.current?.focus()
                  }}
                >
                  Edit question
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
                  Find relevant sections
                </InlineAction>
              </div>
            </div>
          )}
        </div>

        <div
          ref={bottomRef}
          className="sticky bottom-0 mt-8 bg-background/95 pb-5 pt-3 backdrop-blur"
        >
          {showJump && (
            <SquircleButton
              className="mb-3"
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                nearBottom.current = true
                setShowJump(false)
                bottomRef.current?.scrollIntoView({
                  block: "end",
                  behavior: window.matchMedia(
                    "(prefers-reduced-motion: reduce)",
                  ).matches
                    ? "auto"
                    : "smooth",
                })
              }}
            >
              <FiArrowDown aria-hidden />
              Jump to latest
            </SquircleButton>
          )}
          {!capabilities.data?.explanations_enabled && (
            <p role="status" className="mb-3 text-body text-muted-foreground">
              Explanations are paused. Find a section to keep reading the
              published laws.
            </p>
          )}
          <ChatComposer
            inputRef={inputRef}
            autoFocus={!search.c && Boolean(search.fresh)}
            value={draft}
            onChange={setDraft}
            onSubmit={() => void submit(draft)}
            purpose="explanation"
            loading={submitting}
            disabled={
              Boolean(activeRunId) || !capabilities.data?.explanations_enabled
            }
            compact={Boolean(search.c)}
            contextLabel={releaseEditionName(
              conversation.data?.edition_label ?? release.data?.edition_label,
            )}
          />
          {!search.c && (
            <div className="mt-4 flex flex-wrap gap-2">
              {suggestions.map((prompt) => (
                <PromptSuggestion
                  key={prompt}
                  onClick={() => {
                    setDraft(prompt)
                    inputRef.current?.focus()
                  }}
                  type="button"
                >
                  {prompt}
                </PromptSuggestion>
              ))}
            </div>
          )}
          <p className="mt-3 text-label font-normal text-muted-foreground">
            Answers explain published laws in plain language and can miss
            details. Check the sections they link to, and talk to a lawyer about
            your own situation.
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
        explainDisabled={
          Boolean(activeRunId || submitting) ||
          !capabilities.data?.explanations_enabled
        }
      />
    </div>
  )
}
