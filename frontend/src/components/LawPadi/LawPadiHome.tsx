import { useEffect, useState } from "react"
import {
  FiBookmark,
  FiCheck,
  FiCopy,
  FiLoader,
  FiMessageSquare,
  FiShare2,
} from "react-icons/fi"

import { ChatComposer } from "@/components/LawPadi/ChatComposer"
import {
  CitationChip,
  ErrorState,
  IconButton,
  InlineAction,
  OfficialTextBlock,
  PromptSuggestion,
  SkeletonBlock,
  StatusBadge,
  TranslationBlock,
} from "@/components/LawPadi/primitives"
import { SourcePanel } from "@/components/LawPadi/SourcePanel"
import {
  answerStages,
  defaultProvision,
  lowConfidenceMatches,
  promptSuggestions,
} from "@/lib/law-padi-data"
import { cn } from "@/lib/utils"

const defaultQuestion = "Can police check my phone without a reason?"

export function LawPadiHome() {
  const [question, setQuestion] = useState("")
  const [submittedQuestion, setSubmittedQuestion] = useState(defaultQuestion)
  const [isLoading, setIsLoading] = useState(false)
  const [stageIndex, setStageIndex] = useState(0)
  const [sourceOpen, setSourceOpen] = useState(false)
  const [copied, setCopied] = useState<"answer" | "share" | null>(null)

  useEffect(() => {
    if (!isLoading) return

    const interval = window.setInterval(() => {
      setStageIndex((current) => (current + 1) % answerStages.length)
    }, 520)

    const done = window.setTimeout(() => {
      setIsLoading(false)
      setStageIndex(0)
    }, 1900)

    return () => {
      window.clearInterval(interval)
      window.clearTimeout(done)
    }
  }, [isLoading])

  const submitQuestion = () => {
    setSubmittedQuestion(question.trim())
    setQuestion("")
    setSourceOpen(false)
    setIsLoading(true)
  }

  const copyAnswer = async (kind: "answer" | "share") => {
    setCopied(kind)
    await navigator.clipboard?.writeText(
      kind === "answer"
        ? `${submittedQuestion}\n\n${defaultProvision.summary}\n${defaultProvision.citation}`
        : `Law Padi answer: ${defaultProvision.citation}`,
    )
    window.setTimeout(() => setCopied(null), 1200)
  }

  return (
    <div
      className={cn(
        "grid min-h-[calc(100svh-4rem)]",
        sourceOpen ? "xl:grid-cols-[minmax(0,1fr)_380px]" : "xl:grid-cols-1",
      )}
    >
      <section className="min-w-0 overflow-y-auto px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
        <div className="mx-auto w-full max-w-4xl">
          <div className="mb-5 text-[0.72rem] font-bold uppercase text-primary">
            The law, made understandable
          </div>
          <div className="max-w-3xl">
            <h1 className="font-legal text-[2.35rem] leading-[1.03] text-foreground sm:text-[3.35rem]">
              Ask about Nigeria&apos;s Constitution.
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground">
              Find a section, understand your rights, or explore constitutional
              amendments with the exact source alongside every answer.
            </p>
          </div>

          <ChatComposer
            className="mt-9"
            loading={isLoading}
            onChange={setQuestion}
            onSubmit={submitQuestion}
            value={question}
          />

          <fieldset className="mt-5 flex flex-wrap gap-2">
            <legend className="sr-only">Suggested questions</legend>
            {promptSuggestions.map((prompt) => (
              <PromptSuggestion
                key={prompt}
                onClick={() => setQuestion(prompt)}
                type="button"
              >
                {prompt}
              </PromptSuggestion>
            ))}
          </fieldset>

          <div className="mt-7 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="font-semibold text-foreground">Ask in</span>
            <span>English</span>
            <span aria-hidden>|</span>
            <span>Pidgin</span>
            <span aria-hidden>|</span>
            <span>Yorùbá</span>
            <span aria-hidden>|</span>
            <span>Igbo</span>
            <span aria-hidden>|</span>
            <span>Hausa</span>
          </div>

          <div className="mt-12 grid gap-7 border-t border-border pt-7">
            {isLoading ? (
              <div className="grid gap-4">
                <div className="sq-sm inline-flex w-fit items-center gap-2 bg-secondary px-3 py-2 text-xs font-semibold text-muted-foreground">
                  <FiLoader className="size-4 animate-spin" aria-hidden />
                  {answerStages[stageIndex]}...
                </div>
                <SkeletonBlock />
              </div>
            ) : (
              <ActiveAnswer
                copied={copied}
                onCopy={copyAnswer}
                onOpenSource={() => setSourceOpen(true)}
                question={submittedQuestion}
              />
            )}

            <LowConfidenceChoices onOpenSource={() => setSourceOpen(true)} />

            <ErrorState
              action={
                <InlineAction type="button">Search exact sections</InlineAction>
              }
              title="No relevant constitutional provision found"
            >
              Try a broader phrase, a section number, or a topic like privacy,
              elections, police powers or fundamental rights.
            </ErrorState>
          </div>
        </div>
      </section>

      <SourcePanel
        onOpenChange={setSourceOpen}
        open={sourceOpen}
        provision={defaultProvision}
      />
    </div>
  )
}

function ActiveAnswer({
  question,
  copied,
  onCopy,
  onOpenSource,
}: {
  question: string
  copied: "answer" | "share" | null
  onCopy: (kind: "answer" | "share") => void
  onOpenSource: () => void
}) {
  return (
    <article aria-label="Constitutional answer" className="grid gap-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <StatusBadge status="current" />
        <div className="flex gap-1">
          <IconButton
            label={copied === "answer" ? "Answer copied" : "Copy explanation"}
            onClick={() => onCopy("answer")}
            type="button"
          >
            {copied === "answer" ? (
              <FiCheck className="size-4" aria-hidden />
            ) : (
              <FiCopy className="size-4" aria-hidden />
            )}
          </IconButton>
          <IconButton
            label={copied === "share" ? "Share link copied" : "Share answer"}
            onClick={() => onCopy("share")}
            type="button"
          >
            {copied === "share" ? (
              <FiCheck className="size-4" aria-hidden />
            ) : (
              <FiShare2 className="size-4" aria-hidden />
            )}
          </IconButton>
          <IconButton label="Save provision" type="button">
            <FiBookmark className="size-4" aria-hidden />
          </IconButton>
        </div>
      </div>

      <div className="sq-lg border border-border bg-card/70 p-4">
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-muted-foreground">
          <FiMessageSquare className="size-4" aria-hidden />
          Question
        </div>
        <p className="text-sm leading-6 text-foreground">{question}</p>
      </div>

      <div className="max-w-3xl">
        <h2 className="font-legal text-2xl leading-tight text-foreground sm:text-3xl">
          Your privacy is protected, but it is not unlimited.
        </h2>
        <p className="mt-4 text-sm leading-7 text-muted-foreground">
          The Constitution protects the privacy of your home, correspondence,
          telephone conversations and telegraphic communications. This includes
          private information on your phone.{" "}
          <CitationChip onClick={onOpenSource}>§37</CitationChip>
        </p>
        <p className="mt-4 text-sm leading-7 text-muted-foreground">
          Another valid law may still permit access in specific circumstances,
          such as an investigation, but the process must be lawful. The
          Constitution does not give police a general unrestricted power to
          search anyone&apos;s phone.
        </p>
      </div>

      <OfficialTextBlock title="Official wording - Section 37">
        {defaultProvision.officialText}
      </OfficialTextBlock>

      <TranslationBlock />

      <div className="grid gap-3 md:grid-cols-2">
        <section className="sq-lg border border-border bg-card p-5">
          <StatusBadge status="current" />
          <h3 className="mt-4 font-legal text-xl leading-tight text-foreground">
            Current Constitution
          </h3>
          <p className="mt-3 text-sm leading-7 text-muted-foreground">
            Section 37 is presented as current law in this preview corpus. The
            official English text remains the legal anchor for any AI
            explanation.
          </p>
        </section>
        <section className="sq-lg border border-[color:var(--legal-amber)]/25 bg-card p-5">
          <StatusBadge status="proposed" />
          <h3 className="mt-4 font-legal text-xl leading-tight text-foreground">
            Proposed Change
          </h3>
          <p className="mt-3 text-sm leading-7 text-muted-foreground">
            Rights-related proposals must stay visibly separate until they are
            enacted. This preview marks proposals as not currently part of the
            Constitution.
          </p>
        </section>
      </div>

      <div className="flex flex-wrap gap-2">
        <InlineAction onClick={onOpenSource} type="button">
          Show official source
        </InlineAction>
        <InlineAction type="button">How has this section changed?</InlineAction>
        <InlineAction type="button">What limits this right?</InlineAction>
      </div>
    </article>
  )
}

function LowConfidenceChoices({ onOpenSource }: { onOpenSource: () => void }) {
  return (
    <section className="sq-lg border border-border bg-card/70 p-5">
      <h2 className="font-legal text-xl leading-tight text-foreground">
        I found two provisions that may match what you mean.
      </h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        Choose one when a question is incomplete, and Law Padi will ground the
        answer in that exact provision.
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {lowConfidenceMatches.map((match) => (
          <button
            className="sq-md border border-border bg-card p-4 text-left transition hover:border-primary/35 hover:bg-accent focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25"
            key={match.section}
            onClick={onOpenSource}
            type="button"
          >
            <span className="text-xs font-bold text-[color:var(--legal-blue)]">
              {match.section}
            </span>
            <span className="mt-1 block font-semibold text-foreground">
              {match.title}
            </span>
            <span className="mt-1 block text-xs leading-5 text-muted-foreground">
              {match.summary}
            </span>
          </button>
        ))}
      </div>
    </section>
  )
}
