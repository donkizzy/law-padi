import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
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
import {
  lawName,
  pageLabel,
  readableText,
  statusLabel,
} from "@/lib/legal-provisions"
import { referencePath } from "@/lib/seo"
import { EditionNotice } from "./EditionNotice"
import { ProvisionNotices } from "./ProvisionNotices"
import { SourceActions } from "./SourceActions"

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
  const { t } = useTranslation("legal")
  const base = import.meta.env.VITE_API_URL || window.location.origin
  const source = new URL(evidence.source_content_url, base)
  if (evidence.source_page_start)
    source.hash = `page=${evidence.source_page_start}`
  return (
    <div className="grid gap-5">
      <div>
        <p className="mb-2 text-label text-primary">{evidence.citation}</p>
        <h2 className="font-display text-title-3">
          {evidence.title ?? evidence.citation}
        </h2>
        {evidence.ancestor_citations.length > 0 && (
          <p className="mt-2 text-label font-normal text-muted-foreground">
            {evidence.ancestor_citations.join(" · ")}
          </p>
        )}
      </div>
      <div className="grid gap-2">
        <StatusBadge
          status={
            evidence.legal_status === "current" ? "current" : "historical"
          }
          label={statusLabel(
            evidence.legal_status,
            evidence.edition_label,
            evidence,
          )}
        />
        <EditionNotice
          label={evidence.edition_label}
          instrument={evidence}
          historical={evidence.legal_status === "historical"}
        />
        <ProvisionNotices notices={evidence.notices} />
      </div>
      <section>
        <h3 className="mb-3 text-overline uppercase text-muted-foreground">
          {t("source.whatLawSays", { law: lawName(evidence) })}
        </h3>
        <p lang="en" className="whitespace-pre-wrap font-legal text-statute-sm">
          {readableText(evidence.authoritative_text)}
        </p>
      </section>
      <p className="text-label font-normal text-muted-foreground">
        {evidence.source_title} · {evidence.source_authority}
        {evidence.source_page_start
          ? ` · ${pageLabel(evidence.source_page_start)}`
          : ""}
      </p>
      <div className="flex flex-wrap gap-3">
        <InlineAction
          disabled={explainDisabled}
          onClick={() => onExplain(evidence)}
          type="button"
        >
          {t("source.explain")}
        </InlineAction>
        <InlineAction asChild>
          <a
            href={referencePath(
              evidence.canonical_path,
              evidence.release_version,
            )}
          >
            {t("source.openFull")}
          </a>
        </InlineAction>
        <InlineAction asChild>
          <a href={source.href} target="_blank" rel="noopener noreferrer">
            {t("source.originalPdf")}
          </a>
        </InlineAction>
      </div>
      <SourceActions source={evidence} />
    </div>
  )
}

export function ChatEvidencePanel({
  evidence,
  onClose,
  onExplain,
  explainDisabled,
}: Props) {
  const { t } = useTranslation("legal")
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
        aria-label={t("source.details")}
        className="sticky top-16 max-h-[calc(100svh-4rem)] self-start overflow-y-auto border-l border-border bg-sidebar/70 px-6 py-6"
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
        <SheetTitle className="sr-only">{t("source.details")}</SheetTitle>
        <SheetDescription className="sr-only">
          {t("source.evidenceDescription")}
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
