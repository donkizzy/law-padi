import { Link as RouterLink } from "@tanstack/react-router"
import { useMemo, useState } from "react"
import { FiFilter, FiSearch } from "react-icons/fi"
import { LiaBookOpenSolid } from "react-icons/lia"

import {
  EmptyState,
  SectionHeading,
  SegmentedControl,
  StatusBadge,
} from "@/components/LawPadi/primitives"
import { chapters, type LegalStatus } from "@/lib/law-padi-data"
import { cn } from "@/lib/utils"

type StatusFilter = "all" | LegalStatus

const statusOptions: { label: string; value: StatusFilter }[] = [
  { label: "All statuses", value: "all" },
  { label: "Current", value: "current" },
  { label: "Proposed", value: "proposed" },
  { label: "Historical", value: "historical" },
]

export function BrowseConstitution() {
  const [query, setQuery] = useState("")
  const [status, setStatus] = useState<StatusFilter>("all")

  const filteredChapters = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()

    return chapters
      .map((chapter) => ({
        ...chapter,
        provisions: chapter.provisions.filter((provision) => {
          const matchesStatus = status === "all" || provision.status === status
          const searchable = [
            provision.section,
            provision.title,
            provision.topic,
            provision.summary,
            chapter.title,
          ]
            .join(" ")
            .toLowerCase()
          const matchesQuery =
            normalizedQuery.length === 0 || searchable.includes(normalizedQuery)

          return matchesStatus && matchesQuery
        }),
      }))
      .filter((chapter) => chapter.provisions.length > 0)
  }, [query, status])

  return (
    <section className="px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
      <div className="mx-auto w-full max-w-5xl">
        <SectionHeading
          kicker="Constitution navigator"
          title="Browse the Constitution."
        >
          Move through the document by chapter, then open any provision to see
          its wording, status, history and source trail.
        </SectionHeading>

        <div className="mb-7 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <label className="sq-md flex min-h-12 items-center gap-3 border border-border bg-card px-4 text-muted-foreground shadow-[var(--shadow-subtle)]">
            <FiSearch className="size-4" aria-hidden />
            <span className="sr-only">Search provisions</span>
            <input
              className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search sections or topics"
              type="search"
              value={query}
            />
          </label>
          <div className="flex min-w-0 items-center gap-2">
            <FiFilter className="hidden size-4 text-muted-foreground sm:block" />
            <SegmentedControl
              ariaLabel="Filter provisions by legal status"
              onChange={setStatus}
              options={statusOptions}
              value={status}
            />
          </div>
        </div>

        {filteredChapters.length === 0 ? (
          <EmptyState title="No matching provision found">
            Try searching for a section number, a chapter name, or a rights
            topic like privacy, expression or movement.
          </EmptyState>
        ) : (
          <div className="grid gap-3">
            {filteredChapters.map((chapter, index) => (
              <details
                className="sq-lg overflow-hidden border border-border bg-card shadow-[var(--shadow-subtle)]"
                key={chapter.id}
                open={index < 2 || query.length > 0}
              >
                <summary className="flex cursor-pointer list-none items-center gap-4 px-5 py-4 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25">
                  <div className="sq-sm grid size-11 shrink-0 place-items-center bg-accent text-accent-foreground">
                    <LiaBookOpenSolid className="size-5" aria-hidden />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-bold uppercase text-primary">
                      {chapter.number}
                    </div>
                    <h2 className="font-legal text-xl leading-tight text-foreground">
                      {chapter.title}
                    </h2>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {chapter.description}
                    </p>
                  </div>
                  <div className="hidden text-right text-xs font-semibold text-muted-foreground sm:block">
                    {chapter.range}
                  </div>
                </summary>
                <div className="border-t border-border p-2">
                  {chapter.provisions.map((provision) => (
                    <RouterLink
                      className={cn(
                        "sq-md grid gap-3 px-4 py-4 transition hover:bg-secondary focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25",
                        "sm:grid-cols-[6rem_minmax(0,1fr)_auto] sm:items-center",
                      )}
                      key={provision.id}
                      params={{ sectionId: provision.id }}
                      to="/constitution/$sectionId"
                    >
                      <span className="text-sm font-bold text-[color:var(--legal-blue)]">
                        {provision.section}
                      </span>
                      <span className="min-w-0">
                        <span className="block font-semibold text-foreground">
                          {provision.title}
                        </span>
                        <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                          {provision.summary}
                        </span>
                      </span>
                      <StatusBadge
                        className="justify-self-start sm:justify-self-end"
                        label={
                          provision.status === "current"
                            ? "Current law"
                            : undefined
                        }
                        status={provision.status}
                      />
                    </RouterLink>
                  ))}
                </div>
              </details>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
