import { useState } from "react"
import { useTranslation } from "react-i18next"
import { toast } from "sonner"
import type { CitationOutcome, EvidenceItem } from "@/client"
import { EditionNotice } from "@/components/Constitution/EditionNotice"
import {
  ProvisionNotices,
  uniqueNotices,
} from "@/components/Constitution/ProvisionNotices"
import {
  InlineAction,
  PromptSuggestion,
} from "@/components/Constitution/primitives"
import { StatuteText } from "@/components/Constitution/StatuteText"
import { useSavedProvisions } from "@/hooks/useSavedProvisions"
import type { ExplanationAnswer } from "@/lib/answer"
import i18n from "@/lib/i18n"
import { editionNote, shortCitation } from "@/lib/legal-provisions"
import { downloadResearch, evidenceCopy } from "@/lib/research"
import { bestContainingSource } from "@/lib/source-ranking"
import { cn } from "@/lib/utils"

const betaLanguages = new Set(["yo", "ha", "ig"])

const languageNames: Record<string, string> = {
  en: "English",
  pcm: "Pidgin",
  yo: "Yorùbá",
  ha: "Hausa",
  ig: "Igbo",
}

/** The answer as the reader sees it: translated unless they asked for English. */
function readerAnswer(
  answer: ExplanationAnswer,
  english: boolean,
): ExplanationAnswer {
  const translation = answer.translation
  if (!translation || english) return answer
  return {
    ...answer,
    blocks: translation.blocks,
    missing_facts: translation.missing_facts,
    follow_up_questions: translation.follow_up_questions,
  }
}

/** Server notices are English; other languages render them from their code. */
function noticeText(answer: ExplanationAnswer): string | null {
  const code = answer.notice_code
  if (!code || (i18n.resolvedLanguage ?? "en") === "en")
    return answer.notice ?? null
  if (code === "edition") return null
  if (!i18n.exists(`chat:notices.${code}`)) return answer.notice ?? null
  const params = answer.notice_params ?? {}
  const text = i18n.t(`chat:notices.${code}` as "chat:notices.cancelled", {
    choices: params.choices?.join(", "),
  })
  return params.laws?.length
    ? `${text} ${i18n.t("chat:notices.coverage", { laws: params.laws.join(", ") })}`
    : text
}

// Fallbacks for older answers that have no server-provided notice.
export const outcomes = [
  "clarification_required",
  "validation_failed",
  "provider_failure",
  "budget_exhausted",
  "capacity_exhausted",
  "cancelled",
] as const

type Outcome = (typeof outcomes)[number]

const isOutcome = (value: string): value is Outcome =>
  (outcomes as readonly string[]).includes(value)

function AnswerActions({ answer }: { answer: ExplanationAnswer }) {
  const { t } = useTranslation(["chat", "common"])
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
        ? `\n\n${t("answer.dependsOn")}:\n${answer.missing_facts.join("\n")}`
        : ""
      const laws = answer.related_laws?.length
        ? `\n\n${t("answer.otherLaws")}:\n${answer.related_laws.join("\n")}`
        : ""
      await navigator.clipboard.writeText(
        `${explanation || statusMessage(answer)}${facts}${laws}\n\n${t("answer.sources")}:\n${answer.evidence.map(evidenceCopy).join("\n\n")}\n\n${t("answer.notAdvice")}`,
      )
      toast.success(t("actions.copied"))
    } catch {
      toast.error(t("actions.copyFailed"))
    }
  }
  const save = () => {
    try {
      const items = splitSources(answer).cited
      const sources = items.length ? items : answer.evidence.slice(0, 4)
      for (const item of sources)
        if (!isSaved(item.canonical_path, item.release_version))
          toggle(item.canonical_path, item.release_version)
      toast.success(t("actions.sourcesSaved"))
    } catch {
      toast.error(t("actions.saveFailed"))
    }
  }
  return (
    <fieldset className="flex flex-wrap gap-2" aria-label={t("actions.label")}>
      <InlineAction type="button" onClick={() => void copy()}>
        {t("actions.copy")}
      </InlineAction>
      {answer.evidence.length > 0 && (
        <InlineAction type="button" onClick={save}>
          {t("actions.saveSources")}
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
        {t("actions.export")}
      </InlineAction>
    </fieldset>
  )
}

function statusMessage(answer: ExplanationAnswer) {
  const notice = noticeText(answer)
  if (notice) return notice
  const gap = answer.citation_outcomes.find((row) => row.status !== "resolved")
  if (answer.outcome === "insufficient_evidence") {
    if (gap?.message) return gap.message
    return answer.evidence.length
      ? i18n.t("chat:outcome.closest")
      : i18n.t("chat:outcome.noSection")
  }
  return isOutcome(answer.outcome)
    ? i18n.t(`chat:outcome.${answer.outcome}`)
    : i18n.t("chat:outcome.unfinished")
}

function answerEditionNotice(answer: ExplanationAnswer) {
  const notice = noticeText(answer)
  if (answer.blocks.length && notice) return notice
  const instruments = new Map<string, EvidenceItem>()
  for (const item of answer.evidence) {
    if (item.legal_status !== "historical") continue
    const slug = item.instrument_slug || item.canonical_path.split(".")[0]
    if (!instruments.has(slug)) instruments.set(slug, item)
  }
  return [...instruments.values()]
    .map((item) => editionNote(item.edition_label, item))
    .join("\n\n")
}

/** Drop sources whose text sits inside another listed source (35(3) in 35). */
export function withoutContained(items: EvidenceItem[]) {
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
  const { t } = useTranslation(["chat", "common"])
  return (
    <button
      aria-label={
        item.title
          ? t("sources.openTitled", {
              citation: item.citation,
              title: item.title,
            })
          : t("sources.open", { citation: item.citation })
      }
      className="sq-md grid gap-1 border border-border bg-card p-4 text-left hover:border-primary focus-visible:ring-2 focus-visible:ring-ring"
      onClick={() => onSelect(item)}
      type="button"
    >
      <span className="text-label text-primary">{item.citation}</span>
      {item.title && (
        <span className="text-body font-semibold">{item.title}</span>
      )}
      <span
        lang="en"
        className="hidden font-legal text-statute-sm text-muted-foreground sm:line-clamp-2"
      >
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

export function LookupGaps({ outcomes }: { outcomes: CitationOutcome[] }) {
  const { t } = useTranslation(["chat", "common"])
  const gaps = outcomes.filter((item) => item.status !== "resolved")
  if (!gaps.length) return null
  return (
    <section
      aria-label={t("gaps.label")}
      className="sq-md border border-amber-500/40 bg-amber-500/5 p-4"
    >
      <h3 className="text-body font-semibold">{t("gaps.title")}</h3>
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
  const { t } = useTranslation(["chat", "common"])
  if (!laws?.length) return null
  return (
    <section aria-label={t("answer.otherLaws")} className={className}>
      <h3 className="text-body font-semibold">{t("answer.otherLaws")}</h3>
      <p className="mt-1 text-body text-muted-foreground">
        {t("answer.otherLawsBody")}
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
  const { t } = useTranslation(["chat", "common"])
  if (!questions.length) return null
  return (
    <section aria-label={t("followUps.label")} className="grid gap-3">
      <h3 className="text-overline uppercase text-muted-foreground">
        {t("followUps.title")}
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

function TranslationBar({
  answer,
  english,
  onToggle,
}: {
  answer: ExplanationAnswer
  english: boolean
  onToggle: () => void
}) {
  const { t } = useTranslation("chat")
  if ((answer.answer_language ?? "en") === "en") return null
  const translation = answer.translation
  if (!translation)
    return (
      <p className="mb-4 text-label text-muted-foreground" role="note">
        {t("translation.unavailable")}
      </p>
    )
  const name = languageNames[translation.language] ?? translation.language
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 text-label text-muted-foreground">
      <span>{t("translation.label")}</span>
      {betaLanguages.has(translation.language) && (
        <span className="sq-xs border border-border px-1.5 text-overline uppercase">
          {t("translation.beta")}
        </span>
      )}
      <InlineAction type="button" aria-pressed={english} onClick={onToggle}>
        {english
          ? t("translation.showTranslation", { language: name })
          : t("translation.showEnglish")}
      </InlineAction>
    </div>
  )
}

export function AnswerView({
  answer: original,
  onSelect,
  onAsk,
}: {
  answer: ExplanationAnswer
  onSelect: (item: EvidenceItem) => void
  onAsk?: (question: string) => void
}) {
  const { t } = useTranslation(["chat", "common"])
  const [english, setEnglish] = useState(false)
  const answer = readerAnswer(original, english)
  const blocksLanguage =
    original.translation && !english ? original.translation.language : "en"
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
      <section aria-label={t("answer.label")} className="grid gap-5">
        <p className="sq-md bg-secondary p-4 text-body" role="status">
          {statusMessage(answer)}
        </p>
        <RelatedLaws laws={answer.related_laws} />
        <EditionNotice
          label={historical?.edition_label}
          historical={Boolean(historical)}
          notice={answerEditionNotice(answer)}
        />
        <ProvisionNotices
          notices={uniqueNotices(answer.evidence.map((item) => item.notices))}
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
            <StatuteText
              canonicalPath={bestSource.canonical_path}
              className="mt-3 font-legal text-statute-sm"
              text={bestSource.authoritative_text}
            />
            <InlineAction
              className="mt-4"
              onClick={() => onSelect(bestSource)}
              type="button"
            >
              {t("answer.moreAboutSection")}
            </InlineAction>
          </div>
        )}
        <SourceList
          items={others.slice(0, 4)}
          onSelect={onSelect}
          title={t("sources.mayHelp")}
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
    <section aria-label={t("answer.label")} className="grid gap-5">
      <div className="sq-lg border border-border bg-card p-5 sm:p-6">
        <TranslationBar
          answer={original}
          english={english}
          onToggle={() => setEnglish((value) => !value)}
        />
        <div className="grid gap-5" lang={blocksLanguage}>
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
            <h3 className="text-body font-semibold">{t("answer.dependsOn")}</h3>
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
        <ProvisionNotices
          className="mt-3"
          notices={uniqueNotices(cited.map((item) => item.notices))}
        />
      </div>
      <LookupGaps outcomes={answer.citation_outcomes} />
      <AnswerActions answer={answer} />
      <SourceList items={cited} onSelect={onSelect} title={t("sources.used")} />
      {others.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-body text-muted-foreground hover:text-foreground">
            {t("sources.othersCameUp", { count: others.length })}
          </summary>
          <div className="mt-3">
            <SourceList
              items={others}
              onSelect={onSelect}
              title={t("sources.alsoRelated")}
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
