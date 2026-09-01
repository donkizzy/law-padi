import type { ReactNode } from "react"
import { useState } from "react"
import type { IconType } from "react-icons"
import { FiCheck, FiCopy, FiExternalLink } from "react-icons/fi"
import { LiaFileAltSolid, LiaHistorySolid } from "react-icons/lia"

import {
  AmendmentTimeline,
  CloseButton,
  InlineAction,
  StatusBadge,
} from "@/components/LawPadi/primitives"
import type { Provision } from "@/lib/law-padi-data"
import { defaultProvision } from "@/lib/law-padi-data"
import { cn } from "@/lib/utils"

type SourcePanelProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  provision?: Provision
}

export function SourcePanel({
  open,
  onOpenChange,
  provision = defaultProvision,
}: SourcePanelProps) {
  if (!open) return null

  return (
    <>
      <aside className="hidden max-h-[calc(100svh-4rem)] min-h-0 border-l border-border bg-sidebar/70 xl:block">
        <SourcePanelContent
          className="h-full overflow-y-auto px-6 py-8"
          onClose={() => onOpenChange(false)}
          provision={provision}
        />
      </aside>

      <div
        aria-hidden="true"
        className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-sm xl:hidden"
        onClick={() => onOpenChange(false)}
      />
      <section
        aria-label="Legal source inspector"
        className="sq-xl fixed inset-x-0 bottom-0 z-50 max-h-[88svh] overflow-y-auto border border-border bg-card p-5 shadow-[var(--shadow-soft)] xl:hidden"
      >
        <div aria-hidden className="sq-xs mx-auto mb-5 h-1 w-11 bg-border" />
        <SourcePanelContent
          onClose={() => onOpenChange(false)}
          provision={provision}
        />
      </section>
    </>
  )
}

export function SourcePanelContent({
  provision,
  onClose,
  className,
}: {
  provision: Provision
  onClose?: () => void
  className?: string
}) {
  const [copied, setCopied] = useState(false)

  const copyCitation = async () => {
    setCopied(true)
    await navigator.clipboard?.writeText(provision.citation)
    window.setTimeout(() => setCopied(false), 1200)
  }

  return (
    <div className={cn("min-w-0", className)}>
      <div className="mb-7 flex items-start justify-between gap-4">
        <div>
          <div className="mb-2 text-[0.7rem] font-bold uppercase text-[color:var(--legal-blue)]">
            Selected provision
          </div>
          <h2 className="font-legal text-2xl leading-tight text-foreground">
            {provision.section}
          </h2>
        </div>
        {onClose ? <CloseButton onClick={onClose} type="button" /> : null}
      </div>

      <p className="mb-4 text-sm leading-6 text-muted-foreground">
        {provision.sourceTitle}
      </p>
      <StatusBadge status={provision.status} />

      <SourceSection icon={LiaFileAltSolid} title="Official wording">
        <p className="font-legal text-[0.98rem] leading-7 text-foreground/90">
          {provision.officialText}
        </p>
      </SourceSection>

      <SourceSection icon={FiExternalLink} title="Citation and source">
        <MetaRow label="Short citation" value={provision.citation} />
        <MetaRow label="Source" value={provision.sourceAuthority} />
        <MetaRow label="Location" value={provision.sourcePage} />
      </SourceSection>

      <SourceSection icon={LiaHistorySolid} title="Amendment history">
        <AmendmentTimeline events={provision.history} />
      </SourceSection>

      <div className="grid gap-2 pt-2">
        <InlineAction onClick={() => undefined} type="button">
          View source document
        </InlineAction>
        <button
          className="sq-sm inline-flex min-h-10 items-center justify-center gap-2 border border-border bg-card px-3 py-2 text-xs font-semibold text-foreground transition hover:border-primary/30 hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25"
          onClick={copyCitation}
          type="button"
        >
          {copied ? (
            <FiCheck className="size-4" aria-hidden />
          ) : (
            <FiCopy className="size-4" aria-hidden />
          )}
          {copied ? "Citation copied" : "Copy citation"}
        </button>
      </div>
    </div>
  )
}

function SourceSection({
  icon: Icon,
  title,
  children,
}: {
  icon: IconType
  title: string
  children: ReactNode
}) {
  return (
    <section className="mt-6 border-t border-border pt-5">
      <h3 className="mb-3 flex items-center gap-2 text-[0.72rem] font-bold uppercase text-muted-foreground">
        <Icon className="size-4" aria-hidden />
        {title}
      </h3>
      {children}
    </section>
  )
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 py-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="max-w-[12rem] text-right font-semibold text-foreground">
        {value}
      </span>
    </div>
  )
}
