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
import { useChatCapabilities } from "@/hooks/useChatCapabilities"
import { legalError, useProvisionHistory } from "@/hooks/useLegalCorpus"
import { useSavedProvisions } from "@/hooks/useSavedProvisions"
import {
  copyText,
  editionName,
  provisionTitle,
  provisionUrl,
  readableText,
  statusLabel,
} from "@/lib/legal-provisions"
import { EditionNotice } from "./EditionNotice"

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
        to="/constitution"
        search={{ parent: provision.canonical_path, release }}
      >
        {provision.citation}
      </Link>
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
  primary = false,
}: {
  provision: LegalSearchResult
  onOpenSource: () => void
  primary?: boolean
  onRelated?: (query: string) => void
}) {
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
      toast.success(kind === "text" ? "Text copied" : "Link copied")
    } catch {
      toast.error("Couldn't copy. Please try again.")
    }
  }
  const save = () => {
    try {
      toast.success(
        toggle(provision.canonical_path, provision.release_version)
          ? "Saved"
          : "Removed from saved",
      )
    } catch {
      toast.error("Couldn't save on this device.")
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
          label={statusLabel(provision.legal_status, provision.edition_label)}
        />
        <div className="flex gap-1">
          <IconButton
            label={copied === "text" ? "Text copied" : "Copy text"}
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
            label="Copy link"
            onClick={() => copy("share")}
            type="button"
          >
            <FiShare2 aria-hidden />
          </IconButton>
          <IconButton
            label={saved ? "Remove from saved" : "Save"}
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
        <Heading className="font-display text-title-3 sm:text-title-2">
          {provisionTitle(provision)}
        </Heading>
        <p className="mt-3 text-body text-muted-foreground">
          {provision.title ? `${provision.citation} · ` : ""}
          {editionName(provision.edition_label)}
        </p>
      </div>
      <OfficialTextBlock title={`What ${provision.citation} says`}>
        <p className="whitespace-pre-wrap">
          {readableText(provision.authoritative_text)}
        </p>
      </OfficialTextBlock>
      <EditionNotice
        label={provision.edition_label}
        historical={provision.legal_status === "historical"}
      />
      <p className="text-sm text-muted-foreground">
        Source: {provision.source_authority}, {provision.source_title}
        {provision.source_page_start
          ? `, printed page ${provision.source_page_start}`
          : ""}
        .{" "}
        <Link className="text-primary underline" to="/about">
          Source scope and corrections
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
              Read all of {ancestor.citation}
            </summary>
            <p className="mt-4 whitespace-pre-wrap font-legal text-sm leading-7">
              {readableText(ancestor.authoritative_text ?? "")}
            </p>
          </details>
        ))}
      {provision.children.length > 0 && (
        <section
          aria-label="Parts of this section"
          className="sq-md border border-border p-4"
        >
          <h3 className="mb-3 text-sm font-semibold">Parts of this section</h3>
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
              Explain in plain English
            </Link>
          </InlineAction>
        )}
        <InlineAction onClick={onOpenSource} type="button">
          Original document
        </InlineAction>
        <InlineAction
          onClick={() => setHistoryOpen(!historyOpen)}
          type="button"
          aria-expanded={historyOpen}
        >
          Version history
        </InlineAction>
        {onRelated && (enclosing?.title || enclosing?.heading) && (
          <InlineAction
            onClick={() => onRelated((enclosing.title || enclosing.heading)!)}
            type="button"
          >
            Find related sections
          </InlineAction>
        )}
      </div>
      {historyOpen && (
        <section
          aria-label="Version history"
          className="sq-md border border-border p-5"
        >
          <h3 className="mb-3 font-semibold">Versions</h3>
          {history.isPending ? (
            <p>Loading versions…</p>
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
