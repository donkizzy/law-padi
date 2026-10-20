import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
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
import {
  lawName,
  provisionTitle,
  readableText,
  sourceUrl,
  statusLabel,
} from "@/lib/legal-provisions"
import { EditionNotice } from "./EditionNotice"
import { SourceActions } from "./SourceActions"

export function SourcePanel({
  open,
  onOpenChange,
  provision,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  provision: LegalSearchResult
}) {
  const { t } = useTranslation("legal")
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
        aria-label={t("source.details")}
        className="sticky top-16 max-h-[calc(100svh-4rem)] self-start overflow-y-auto border-l border-border bg-sidebar/70 px-6 py-6"
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
        <SheetTitle className="sr-only">{t("source.details")}</SheetTitle>
        <SheetDescription className="sr-only">
          {t("source.description")}
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
  const { t } = useTranslation("legal")
  return (
    <div className="grid gap-5">
      <div>
        <p className="mb-2 text-label text-primary">{provision.citation}</p>
        <h2 className="font-display text-title-3">
          {provisionTitle(provision)}
        </h2>
      </div>
      <StatusBadge
        status={provision.legal_status === "current" ? "current" : "historical"}
        label={statusLabel(
          provision.legal_status,
          provision.edition_label,
          provision,
        )}
      />
      <EditionNotice
        label={provision.edition_label}
        instrument={provision}
        historical={provision.legal_status === "historical"}
      />
      <SourceActions source={provision} />
      <section>
        <h3 className="mb-3 text-xs font-bold uppercase text-muted-foreground">
          {t("source.whatLawSays", { law: lawName(provision) })}
        </h3>
        <p
          lang="en"
          className="whitespace-pre-wrap font-legal text-sm leading-7"
        >
          {readableText(provision.authoritative_text)}
        </p>
      </section>
      <dl className="grid gap-3 text-sm">
        <div>
          <dt className="text-muted-foreground">{t("source.citation")}</dt>
          <dd className="font-semibold">{provision.citation}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t("source.document")}</dt>
          <dd>{provision.source_title}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t("source.authority")}</dt>
          <dd>{provision.source_authority}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t("source.location")}</dt>
          <dd>
            {provision.source_page_start
              ? t("source.pages", {
                  pages: `${provision.source_page_start}${provision.source_page_end && provision.source_page_end !== provision.source_page_start ? `–${provision.source_page_end}` : ""}`,
                })
              : t("source.pageNotRecorded")}
          </dd>
        </div>
      </dl>
      <InlineAction asChild>
        <a
          href={sourceUrl(provision)}
          target="_blank"
          rel="noopener noreferrer"
        >
          {t("source.originalPdf")}
        </a>
      </InlineAction>
    </div>
  )
}
