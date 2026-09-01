import { useMemo, useState } from "react"
import { FiColumns } from "react-icons/fi"
import { LiaCalendarAltSolid, LiaGavelSolid } from "react-icons/lia"

import {
  AmendmentTimeline,
  InlineAction,
  SectionHeading,
  SegmentedControl,
  SquircleButton,
  StatusBadge,
  VersionDiff,
} from "@/components/LawPadi/primitives"
import { type Amendment, amendments } from "@/lib/law-padi-data"
import { cn } from "@/lib/utils"

type AmendmentFilter = "all" | "enacted" | "proposed"

const amendmentOptions: { label: string; value: AmendmentFilter }[] = [
  { label: "All", value: "all" },
  { label: "Enacted", value: "enacted" },
  { label: "Proposed", value: "proposed" },
]

export function AmendmentsView() {
  const [filter, setFilter] = useState<AmendmentFilter>("all")
  const [comparisonOpen, setComparisonOpen] = useState(true)

  const enacted = useMemo(
    () => amendments.filter((amendment) => amendment.status === "current"),
    [],
  )
  const proposed = useMemo(
    () => amendments.filter((amendment) => amendment.status === "proposed"),
    [],
  )

  return (
    <section className="px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
      <div className="mx-auto w-full max-w-6xl">
        <SectionHeading
          action={
            <SegmentedControl
              ariaLabel="Filter amendments"
              onChange={setFilter}
              options={amendmentOptions}
              value={filter}
            />
          }
          kicker="Constitutional change"
          title="Amendments, clearly separated."
        >
          See what has become law, what is historical, and what is still only
          proposed.
        </SectionHeading>

        {(filter === "all" || filter === "enacted") && (
          <AmendmentSection
            amendments={enacted}
            onOpenComparison={() => setComparisonOpen(true)}
            title="Enacted alterations"
          />
        )}

        {(filter === "all" || filter === "proposed") && (
          <AmendmentSection
            amendments={proposed}
            proposed
            title="Proposed alterations"
          />
        )}

        <section className="mt-8 grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="sq-lg border border-border bg-card p-5 shadow-[var(--shadow-subtle)]">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="mb-2 flex items-center gap-2 text-[0.72rem] font-bold uppercase text-muted-foreground">
                  <FiColumns className="size-4" aria-hidden />
                  Version comparison
                </div>
                <h2 className="font-legal text-2xl leading-tight text-foreground">
                  What changed?
                </h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Changed by: First Alteration Act. Effective: 2010.
                </p>
              </div>
              <SquircleButton
                onClick={() => setComparisonOpen((open) => !open)}
                type="button"
                variant="outline"
              >
                {comparisonOpen ? "Hide diff" : "Show diff"}
              </SquircleButton>
            </div>
            {comparisonOpen ? (
              <VersionDiff
                current="The court may make rules for regulating its practice and procedure, subject to the provisions of this Constitution."
                previous="The court may make rules for regulating its own procedure."
              />
            ) : null}
          </div>

          <ProposedBillDetail amendment={proposed[0]} />
        </section>
      </div>
    </section>
  )
}

function AmendmentSection({
  title,
  amendments: items,
  proposed = false,
  onOpenComparison,
}: {
  title: string
  amendments: Amendment[]
  proposed?: boolean
  onOpenComparison?: () => void
}) {
  return (
    <section className="mb-8">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="font-legal text-2xl leading-tight text-foreground">
          {title}
        </h2>
        <span className="text-xs font-semibold text-muted-foreground">
          {items.length} items
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {items.map((amendment) => (
          <article
            className={cn(
              "sq-lg border bg-card p-5 shadow-[var(--shadow-subtle)] transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-soft)]",
              proposed
                ? "border-[color:var(--legal-amber)]/25"
                : "border-border",
            )}
            key={amendment.id}
          >
            <StatusBadge status={amendment.status} />
            <h3 className="mt-4 font-legal text-xl leading-tight text-foreground">
              {amendment.title}
            </h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {amendment.summary}
            </p>
            <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-border pt-4 text-xs text-muted-foreground">
              <span className="sq-xs inline-flex min-h-7 items-center gap-1 bg-secondary px-2 font-semibold">
                <LiaCalendarAltSolid className="size-3.5" aria-hidden />
                {amendment.year}
              </span>
              <span className="sq-xs inline-flex min-h-7 items-center gap-1 bg-secondary px-2 font-semibold">
                <LiaGavelSolid className="size-3.5" aria-hidden />
                {amendment.stage}
              </span>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {amendment.affectedSections.map((section) => (
                <span
                  className="sq-xs border border-border bg-secondary px-2 py-1 text-xs font-semibold text-muted-foreground"
                  key={section}
                >
                  {section}
                </span>
              ))}
            </div>
            <div className="mt-5">
              {proposed ? (
                <InlineAction type="button">
                  View proposal timeline
                </InlineAction>
              ) : (
                <InlineAction onClick={onOpenComparison} type="button">
                  View changes
                </InlineAction>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

function ProposedBillDetail({ amendment }: { amendment?: Amendment }) {
  if (!amendment) return null

  return (
    <aside className="sq-lg border border-[color:var(--legal-amber)]/25 bg-card p-5 shadow-[var(--shadow-subtle)]">
      <StatusBadge status="proposed" />
      <h2 className="mt-4 font-legal text-xl leading-tight text-foreground">
        Not currently part of the Constitution
      </h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        {amendment.title} remains a proposal until every constitutional
        alteration stage is complete.
      </p>
      <div className="mt-5">
        <AmendmentTimeline events={amendment.timeline} />
      </div>
    </aside>
  )
}
