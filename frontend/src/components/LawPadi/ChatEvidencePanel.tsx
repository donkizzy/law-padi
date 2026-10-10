import { useEffect, useRef, useState } from "react"
import type { EvidenceItem } from "@/client"
import {
  CloseButton,
  InlineAction,
  StatusBadge,
} from "@/components/LawPadi/primitives"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet"

type Props = {
  evidence: EvidenceItem | null
  onClose: () => void
  onExplain: (evidence: EvidenceItem) => void
  explainDisabled: boolean
}

function SourceContent({
  evidence,
  onExplain,
  explainDisabled,
}: {
  evidence: EvidenceItem
  onExplain: (evidence: EvidenceItem) => void
  explainDisabled: boolean
}) {
  const base = import.meta.env.VITE_API_URL || window.location.origin
  const source = new URL(evidence.source_content_url, base)
  if (evidence.source_page_start)
    source.hash = `page=${evidence.source_page_start}`
  return (
    <div className="grid gap-5">
      <div>
        <p className="mb-2 text-xs font-bold uppercase text-primary">
          Source context
        </p>
        <h2 className="font-legal text-2xl">{evidence.citation}</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {evidence.ancestor_citations.join(" · ")}
        </p>
      </div>
      <StatusBadge
        status={evidence.legal_status === "current" ? "current" : "historical"}
        label={
          evidence.legal_status === "historical"
            ? "Historical source edition"
            : evidence.legal_status
        }
      />
      <p className="text-sm text-muted-foreground">{evidence.edition_label}</p>
      <section>
        <h3 className="mb-3 text-xs font-bold uppercase text-muted-foreground">
          Stored English wording
        </h3>
        <p className="whitespace-pre-wrap font-legal text-sm leading-7">
          {evidence.authoritative_text}
        </p>
      </section>
      <dl className="grid gap-2 text-sm">
        <div>
          <dt className="text-muted-foreground">Document</dt>
          <dd>{evidence.source_title}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Authority</dt>
          <dd>{evidence.source_authority}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Page</dt>
          <dd>{evidence.source_page_start ?? "Not recorded"}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Release</dt>
          <dd>{evidence.release_version}</dd>
        </div>
      </dl>
      <div className="flex flex-wrap gap-3">
        <InlineAction
          disabled={explainDisabled}
          onClick={() => onExplain(evidence)}
          type="button"
        >
          Explain this identity
        </InlineAction>
        <InlineAction asChild>
          <a href={source.href} target="_blank" rel="noopener noreferrer">
            View source document
          </a>
        </InlineAction>
        <InlineAction asChild>
          <a
            href={`/constitution/${encodeURIComponent(evidence.canonical_path)}?release=${encodeURIComponent(evidence.release_version)}`}
          >
            Open provision
          </a>
        </InlineAction>
      </div>
    </div>
  )
}

export function ChatEvidencePanel({
  evidence,
  onClose,
  onExplain,
  explainDisabled,
}: Props) {
  const [desktop, setDesktop] = useState(
    () => window.matchMedia("(min-width: 1280px)").matches,
  )
  const opener = useRef<HTMLElement | null>(null)
  useEffect(() => {
    const media = window.matchMedia("(min-width: 1280px)")
    const update = () => setDesktop(media.matches)
    media.addEventListener("change", update)
    return () => media.removeEventListener("change", update)
  }, [])
  useEffect(() => {
    if (!evidence || !desktop) return
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    document.addEventListener("keydown", onEscape)
    return () => document.removeEventListener("keydown", onEscape)
  }, [desktop, evidence, onClose])
  if (desktop)
    return evidence ? (
      <aside
        aria-label="Legal source inspector"
        className="max-h-[calc(100svh-4rem)] overflow-y-auto border-l border-border bg-sidebar/70 px-6 py-8"
      >
        <div className="mb-5 flex justify-end">
          <CloseButton onClick={onClose} type="button" />
        </div>
        <SourceContent
          evidence={evidence}
          onExplain={onExplain}
          explainDisabled={explainDisabled}
        />
      </aside>
    ) : null
  return (
    <Sheet open={Boolean(evidence)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="bottom"
        className="sq-xl max-h-[88svh] overflow-y-auto p-5"
        onOpenAutoFocus={() => {
          opener.current =
            document.activeElement instanceof HTMLElement
              ? document.activeElement
              : null
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault()
          opener.current?.focus()
        }}
      >
        <SheetTitle className="sr-only">Legal source inspector</SheetTitle>
        <SheetDescription className="sr-only">
          Stored wording and original source document.
        </SheetDescription>
        {evidence && (
          <SourceContent
            evidence={evidence}
            onExplain={onExplain}
            explainDisabled={explainDisabled}
          />
        )}
      </SheetContent>
    </Sheet>
  )
}
