import { Link } from "@tanstack/react-router"
import { useState } from "react"
import { FiBookmark, FiCheck, FiCopy, FiShare2 } from "react-icons/fi"
import { toast } from "sonner"
import type { LegalSearchResult, ProvisionReference } from "@/client"
import {
  CitationChip,
  IconButton,
  InlineAction,
  OfficialTextBlock,
  StatusBadge,
} from "@/components/LawPadi/primitives"
import { legalError, useProvisionHistory } from "@/hooks/useLegalCorpus"
import { useSavedProvisions } from "@/hooks/useSavedProvisions"
import { copyText, provisionUrl } from "@/lib/legal-provisions"

export function ProvisionLink({
  provision,
  release,
}: {
  provision: ProvisionReference
  release: string
}) {
  if (!provision.has_text)
    return (
      <span className="text-sm font-semibold text-muted-foreground">
        {provision.citation}
      </span>
    )
  return (
    <Link
      className="sq-sm text-sm font-semibold text-primary hover:underline focus-visible:ring-2 focus-visible:ring-ring"
      to="/constitution/$sectionId"
      params={{ sectionId: provision.canonical_path }}
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
}: {
  provision: LegalSearchResult
  onOpenSource: () => void
  onRelated?: (query: string) => void
}) {
  const [copied, setCopied] = useState<"text" | "share" | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const history = useProvisionHistory(
    provision.canonical_path,
    provision.release_version,
    historyOpen,
  )
  const { isSaved, toggle } = useSavedProvisions()
  const saved = isSaved(provision.canonical_path, provision.release_version)
  const copy = async (kind: "text" | "share") => {
    try {
      await navigator.clipboard.writeText(
        kind === "text" ? copyText(provision) : provisionUrl(provision),
      )
      setCopied(kind)
      toast.success(
        kind === "text" ? "Wording copied" : "Provision link copied",
      )
    } catch {
      toast.error("Clipboard access failed. Please try again.")
    }
  }
  const save = () => {
    try {
      toast.success(
        toggle(provision.canonical_path, provision.release_version)
          ? "Provision saved in this browser"
          : "Provision removed from saved",
      )
    } catch {
      toast.error("Your browser could not save this provision.")
    }
  }
  const enclosing = [...provision.ancestors, provision].find(
    (item) => item.kind === "section",
  )
  return (
    <article aria-label="Constitutional provision" className="grid gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <StatusBadge
          status={
            provision.legal_status === "current"
              ? "current"
              : provision.legal_status === "proposed"
                ? "proposed"
                : "historical"
          }
          label={
            provision.legal_status === "historical"
              ? "Historical source edition"
              : provision.legal_status.replace(/_/g, " ")
          }
        />
        <div className="flex gap-1">
          <IconButton
            label={copied === "text" ? "Wording copied" : "Copy wording"}
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
            label="Share provision"
            onClick={() => copy("share")}
            type="button"
          >
            <FiShare2 aria-hidden />
          </IconButton>
          <IconButton
            label={saved ? "Unsave provision" : "Save provision"}
            aria-pressed={saved}
            onClick={save}
            type="button"
          >
            {saved ? <FiCheck aria-hidden /> : <FiBookmark aria-hidden />}
          </IconButton>
        </div>
      </div>
      <nav
        aria-label="Provision hierarchy"
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
        <CitationChip onClick={onOpenSource}>{provision.citation}</CitationChip>
      </nav>
      <div>
        <h2 className="font-legal text-2xl leading-tight sm:text-3xl">
          {provision.heading || provision.citation}
        </h2>
        <p className="mt-3 text-sm text-muted-foreground">
          {provision.edition_label} · {provision.source_authority}
        </p>
      </div>
      <OfficialTextBlock
        title={`Stored English wording — ${provision.citation}`}
      >
        <p className="whitespace-pre-wrap">{provision.authoritative_text}</p>
      </OfficialTextBlock>
      {provision.ancestors
        .filter((ancestor) => ancestor.authoritative_text)
        .map((ancestor) => (
          <details
            className="sq-md border border-border bg-card p-4"
            key={ancestor.id}
          >
            <summary className="cursor-pointer text-sm font-semibold">
              Context from {ancestor.citation}
            </summary>
            <p className="mt-4 whitespace-pre-wrap font-legal text-sm leading-7">
              {ancestor.authoritative_text}
            </p>
          </details>
        ))}
      {provision.children.length > 0 && (
        <section
          aria-label="Child provisions"
          className="sq-md border border-border p-4"
        >
          <h3 className="mb-3 text-sm font-semibold">Within this provision</h3>
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
        <InlineAction onClick={onOpenSource} type="button">
          Show official source
        </InlineAction>
        <InlineAction
          onClick={() => setHistoryOpen(!historyOpen)}
          type="button"
          aria-expanded={historyOpen}
        >
          View stored version history
        </InlineAction>
        {onRelated && enclosing?.heading && (
          <InlineAction
            onClick={() => onRelated(enclosing.heading!)}
            type="button"
          >
            Find related provisions
          </InlineAction>
        )}
      </div>
      {historyOpen && (
        <section
          aria-label="Stored version history"
          className="sq-md border border-border p-5"
        >
          <h3 className="mb-3 font-semibold">Stored published versions</h3>
          {history.isPending ? (
            <p>Loading version history…</p>
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
                    to="/constitution/$sectionId"
                    params={{ sectionId: version.canonical_path }}
                    search={{ release: version.release_version }}
                  >
                    {version.citation} · {version.edition_label} ·{" "}
                    {version.legal_status}
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
