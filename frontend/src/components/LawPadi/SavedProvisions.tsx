import { Link as RouterLink } from "@tanstack/react-router"
import { useMemo, useState } from "react"
import { FiSearch } from "react-icons/fi"
import { LiaBookmarkSolid } from "react-icons/lia"

import {
  EmptyState,
  SectionHeading,
  SquircleButton,
  StatusBadge,
} from "@/components/LawPadi/primitives"
import { savedProvisions } from "@/lib/law-padi-data"

export function SavedProvisions() {
  const [query, setQuery] = useState("")

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return savedProvisions

    return savedProvisions.filter(({ provision, note }) =>
      [provision.section, provision.title, provision.summary, note]
        .join(" ")
        .toLowerCase()
        .includes(normalized),
    )
  }, [query])

  return (
    <section className="px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
      <div className="mx-auto w-full max-w-5xl">
        <SectionHeading kicker="Saved research" title="Saved provisions.">
          Keep important sections close while you compare sources, write notes
          or continue a constitutional-law thread.
        </SectionHeading>

        <label className="sq-md mb-6 flex min-h-12 max-w-lg items-center gap-3 border border-border bg-card px-4 text-muted-foreground shadow-[var(--shadow-subtle)]">
          <FiSearch className="size-4" aria-hidden />
          <span className="sr-only">Search saved provisions</span>
          <input
            className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search saved provisions"
            type="search"
            value={query}
          />
        </label>

        {filtered.length === 0 ? (
          <EmptyState title="No saved provision matches">
            Search by topic, citation or the note you attached to the provision.
          </EmptyState>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {filtered.map(({ id, provision, note }) => (
              <article
                className="sq-lg border border-border bg-card p-5 shadow-[var(--shadow-subtle)]"
                key={id}
              >
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div className="sq-sm grid size-11 place-items-center bg-accent text-accent-foreground">
                    <LiaBookmarkSolid className="size-5" aria-hidden />
                  </div>
                  <StatusBadge status={provision.status} />
                </div>
                <p className="text-sm font-bold text-[color:var(--legal-blue)]">
                  {provision.section}
                </p>
                <h2 className="mt-1 font-legal text-xl leading-tight text-foreground">
                  {provision.title}
                </h2>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  {provision.summary}
                </p>
                <p className="mt-4 text-xs font-semibold text-muted-foreground">
                  {note}
                </p>
                <SquircleButton
                  asChild
                  className="mt-5 w-full"
                  variant="outline"
                >
                  <RouterLink
                    params={{ sectionId: provision.id }}
                    to="/constitution/$sectionId"
                  >
                    Open provision
                  </RouterLink>
                </SquircleButton>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
