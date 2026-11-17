import { Link } from "@tanstack/react-router"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { FiBookmark, FiCheck, FiCopy, FiShare2 } from "react-icons/fi"
import { toast } from "sonner"
import type { LegalSearchResult, ProvisionReference } from "@/client"
import {
  CitationChip,
  IconButton,
  InlineAction,
  OfficialTextBlock,
  StatusBadge,
} from "@/components/Constitution/primitives"
import { useChatCapabilities } from "@/hooks/useChatCapabilities"
import { legalError, useProvisionHistory } from "@/hooks/useLegalCorpus"
import { useSavedProvisions } from "@/hooks/useSavedProvisions"
import {
  copyText,
  editionName,
  instrumentSlug,
  provisionTitle,
  provisionUrl,
  shortCitation,
  statusLabel,
} from "@/lib/legal-provisions"
import { EditionNotice } from "./EditionNotice"
import { ProvisionNotices } from "./ProvisionNotices"
import { StatuteText } from "./StatuteText"

export function ProvisionLink({
  provision,
  release,
}: {
  provision: ProvisionReference
  release: string
}) {
  if (!provision.has_text)
    return (
      <Link
        className="text-sm font-semibold text-primary hover:underline"
        to="/laws/$instrument"
        params={{ instrument: instrumentSlug(provision) }}
        search={{ parent: provision.canonical_path, release }}
      >
        {provision.citation}
      </Link>
    )
  return (
    <Link
      className="sq-sm text-sm font-semibold text-primary hover:underline focus-visible:ring-2 focus-visible:ring-ring"
      to="/laws/$instrument/$sectionId"
      params={{
        instrument: instrumentSlug(provision),
        sectionId: provision.canonical_path,
      }}
      search={{ release }}
    >
      {provision.citation}
    </Link>
  )
}

export function ProvisionView({
  provision,
  onOpenSource,
  onRelated,
  primary = false,
}: {
  provision: LegalSearchResult
  onOpenSource: () => void
  primary?: boolean
  onRelated?: (query: string) => void
}) {
  const { t } = useTranslation("legal")
  const Heading = primary ? "h1" : "h2"
  const [copied, setCopied] = useState<"text" | "share" | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const history = useProvisionHistory(
    provision.canonical_path,
    provision.release_version,
    historyOpen,
  )
  const { isSaved, toggle } = useSavedProvisions()
  const capabilities = useChatCapabilities()
  const saved = isSaved(provision.canonical_path, provision.release_version)
  const copy = async (kind: "text" | "share") => {
    try {
      await navigator.clipboard.writeText(
        kind === "text" ? copyText(provision) : provisionUrl(provision),
      )
      setCopied(kind)
      toast.success(
        kind === "text" ? t("provision.textCopied") : t("provision.linkCopied"),
      )
    } catch {
      toast.error(t("provision.copyFailed"))
    }
  }
  const save = () => {
    try {
      toast.success(
        toggle(provision.canonical_path, provision.release_version)
          ? t("provision.saved")
          : t("provision.removed"),
      )
    } catch {
      toast.error(t("provision.saveFailed"))
    }
  }
  const enclosing = [...provision.ancestors, provision].find(
    (item) => item.kind === "section",
  )
  return (
    <article
      aria-label={
        instrumentSlug(provision) === "constitution-1999"
          ? t("provision.constitutional")
          : t("provision.legal")
      }
      className="grid gap-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <StatusBadge
          status={
            provision.legal_status === "current"
              ? "current"
              : provision.legal_status === "proposed"
                ? "proposed"
                : "historical"
          }
          label={statusLabel(
            provision.legal_status,
            provision.edition_label,
            provision,
          )}
        />
        <div className="flex gap-1">
          <IconButton
            label={
              copied === "text"
                ? t("provision.textCopied")
                : t("provision.copyText")
            }
            onClick={() => copy("text")}
            type="button"
          >
            {copied === "text" ? (
              <FiCheck aria-hidden />
            ) : (
              <FiCopy aria-hidden />
            )}
          </IconButton>
          <IconButton
            label={t("provision.copyLink")}
            onClick={() => copy("share")}
            type="button"
          >
            <FiShare2 aria-hidden />
          </IconButton>
          <IconButton
            label={saved ? t("provision.unsave") : t("provision.save")}
            aria-pressed={saved}
            onClick={save}
            type="button"
          >
            {saved ? <FiCheck aria-hidden /> : <FiBookmark aria-hidden />}
          </IconButton>
        </div>
      </div>
      <nav
        aria-label={t("provision.hierarchy")}
        className="flex flex-wrap items-center gap-2"
      >
        {provision.ancestors.map((ancestor) => (
          <span key={ancestor.id} className="inline-flex items-center gap-2">
            <ProvisionLink
              provision={ancestor}
              release={provision.release_version}
            />
            <span aria-hidden>→</span>
          </span>
        ))}
        <CitationChip onClick={onOpenSource}>
          {shortCitation(provision)}
        </CitationChip>
      </nav>
      <div>
        <Heading className="font-display text-title-3 sm:text-title-2">
          {provisionTitle(provision)}
        </Heading>
        <p className="mt-3 text-body text-muted-foreground">
          {provision.title ? `${provision.citation} · ` : ""}
          {editionName(provision.edition_label, provision)}
        </p>
      </div>
      <OfficialTextBlock
        title={t("source.whatLawSays", { law: provision.citation })}
      >
        <StatuteText
          canonicalPath={provision.canonical_path}
          text={provision.authoritative_text}
        />
      </OfficialTextBlock>
      <EditionNotice
        label={provision.edition_label}
        instrument={provision}
        historical={provision.legal_status === "historical"}
      />
      <ProvisionNotices notices={provision.notices} />
      <p className="text-sm text-muted-foreground">
        {provision.source_page_start
          ? t("provision.sourcePage", {
              authority: provision.source_authority,
              title: provision.source_title,
              page: provision.source_page_start,
            })
          : t("provision.source", {
              authority: provision.source_authority,
              title: provision.source_title,
            })}{" "}
        <Link className="text-primary underline" to="/about">
          {t("provision.scopeLink")}
        </Link>
      </p>
      {provision.ancestors
        .filter((ancestor) => ancestor.authoritative_text)
        .map((ancestor) => (
          <details
            className="sq-md border border-border bg-card p-4"
            key={ancestor.id}
          >
            <summary className="cursor-pointer text-sm font-semibold">
              {t("provision.readAll", { citation: ancestor.citation })}
            </summary>
            <StatuteText
              canonicalPath={ancestor.canonical_path}
              className="mt-4 font-legal text-sm leading-7"
              text={ancestor.authoritative_text ?? ""}
            />
          </details>
        ))}
      {provision.children.length > 0 && (
        <section
          aria-label={t("provision.parts")}
          className="sq-md border border-border p-4"
        >
          <h3 className="mb-3 text-sm font-semibold">{t("provision.parts")}</h3>
          <div className="flex flex-wrap gap-4">
            {provision.children.map((child) => (
              <ProvisionLink
                key={child.id}
                provision={child}
                release={provision.release_version}
              />
            ))}
          </div>
        </section>
      )}
      <div className="flex flex-wrap gap-2">
        {capabilities.data?.explanations_enabled && (
          <InlineAction asChild>
            <Link
              to="/"
              search={{
                c: undefined,
                q: provision.citation,
                mode: "auto",
                release: provision.release_version,
                selected: provision.provision_version_id,
                intent: "ask",
                fresh: crypto.randomUUID(),
              }}
            >
              {t("provision.explain")}
            </Link>
          </InlineAction>
        )}
        <InlineAction onClick={onOpenSource} type="button">
          {t("provision.original")}
        </InlineAction>
        <InlineAction
          onClick={() => setHistoryOpen(!historyOpen)}
          type="button"
          aria-expanded={historyOpen}
        >
          {t("provision.history")}
        </InlineAction>
        {onRelated && (enclosing?.title || enclosing?.heading) && (
          <InlineAction
            onClick={() => onRelated((enclosing.title || enclosing.heading)!)}
            type="button"
          >
            {t("provision.related")}
          </InlineAction>
        )}
      </div>
      {historyOpen && (
        <section
          aria-label={t("provision.history")}
          className="sq-md border border-border p-5"
        >
          <h3 className="mb-3 font-semibold">{t("provision.versions")}</h3>
          {history.isPending ? (
            <p>{t("provision.loadingVersions")}</p>
          ) : history.isError ? (
            <p role="alert">{legalError(history.error)}</p>
          ) : (
            <>
              <p className="mb-3 text-sm text-muted-foreground">
                {history.data.message}
              </p>
              <div className="grid gap-3">
                {history.data.data.map((version) => (
                  <Link
                    key={version.provision_version_id}
                    className="text-sm text-primary hover:underline"
                    to="/laws/$instrument/$sectionId"
                    params={{
                      instrument: instrumentSlug(version),
                      sectionId: version.canonical_path,
                    }}
                    search={{ release: version.release_version }}
                  >
                    {version.citation} ·{" "}
                    {statusLabel(version.legal_status, version.edition_label)}
                  </Link>
                ))}
              </div>
            </>
          )}
        </section>
      )}
    </article>
  )
}
