import { useEffect, useRef, useState } from "react"
import type { LegalSearchResult } from "@/client"
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
import { sourceUrl } from "@/lib/legal-provisions"

export function SourcePanel({
  open,
  onOpenChange,
  provision,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  provision: LegalSearchResult
}) {
  const [desktop, setDesktop] = useState(
    () => window.matchMedia("(min-width: 1280px)").matches,
  )
  const opener = useRef<HTMLElement | null>(null)
  useEffect(() => {
    const media = window.matchMedia("(min-width: 1280px)")
    const changed = () => setDesktop(media.matches)
    media.addEventListener("change", changed)
    return () => media.removeEventListener("change", changed)
  }, [])
  useEffect(() => {
    if (!open || !desktop) return
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onOpenChange(false)
    }
    document.addEventListener("keydown", handleEscape)
    return () => document.removeEventListener("keydown", handleEscape)
  }, [open, desktop, onOpenChange])
  if (desktop)
    return open ? (
      <aside
        aria-label="Legal source inspector"
        className="max-h-[calc(100svh-4rem)] overflow-y-auto border-l border-border bg-sidebar/70 px-6 py-8"
      >
        <div className="mb-5 flex justify-end">
          <CloseButton onClick={() => onOpenChange(false)} type="button" />
        </div>
        <SourcePanelContent provision={provision} />
      </aside>
    ) : null
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
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
          Stored wording, historical edition, citation, and original source
          document.
        </SheetDescription>
        <SourcePanelContent provision={provision} />
      </SheetContent>
    </Sheet>
  )
}

export function SourcePanelContent({
  provision,
}: {
  provision: LegalSearchResult
}) {
  return (
    <div className="grid gap-5">
      <div>
        <p className="mb-2 text-xs font-bold uppercase text-primary">
          Selected provision
        </p>
        <h2 className="font-legal text-2xl">{provision.citation}</h2>
      </div>
      <StatusBadge
        status={provision.legal_status === "current" ? "current" : "historical"}
        label={
          provision.legal_status === "historical"
            ? "Historical source edition"
            : provision.legal_status
        }
      />
      <p className="text-sm leading-6 text-muted-foreground">
        {provision.edition_label}
      </p>
      <section>
        <h3 className="mb-3 text-xs font-bold uppercase text-muted-foreground">
          Official source wording
        </h3>
        <p className="whitespace-pre-wrap font-legal text-sm leading-7">
          {provision.authoritative_text}
        </p>
      </section>
      <dl className="grid gap-3 text-sm">
        <div>
          <dt className="text-muted-foreground">Citation</dt>
          <dd className="font-semibold">{provision.citation}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Document</dt>
          <dd>{provision.source_title}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Authority</dt>
          <dd>{provision.source_authority}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Location</dt>
          <dd>
            {provision.source_page_start
              ? `PDF page ${provision.source_page_start}${provision.source_page_end && provision.source_page_end !== provision.source_page_start ? `–${provision.source_page_end}` : ""}`
              : "Page not recorded"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Release</dt>
          <dd className="break-all">{provision.release_version}</dd>
        </div>
      </dl>
      <InlineAction asChild>
        <a
          href={sourceUrl(provision)}
          target="_blank"
          rel="noopener noreferrer"
        >
          View source document
        </a>
      </InlineAction>
    </div>
  )
}
