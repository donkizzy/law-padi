import { useQueries } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { useState } from "react"
import { toast } from "sonner"
import { LegalService } from "@/client"
import {
  EmptyState,
  InlineAction,
  SectionHeading,
  StatusBadge,
} from "@/components/LawPadi/primitives"
import { legalError, type useProvision } from "@/hooks/useLegalCorpus"
import { type Bookmark, useSavedProvisions } from "@/hooks/useSavedProvisions"
import { provisionTitle, statusLabel } from "@/lib/legal-provisions"
import { downloadResearch } from "@/lib/research"
import { EditionNotice } from "./EditionNotice"

export function SavedProvisions() {
  const { bookmarks, storageError } = useSavedProvisions()
  const [query, setQuery] = useState("")
  const details = useQueries({
    queries: bookmarks.map((bookmark) => ({
      queryKey: [
        "legal",
        "provision",
        bookmark.canonical_path,
        bookmark.release_version,
      ],
      queryFn: async ({ signal }: { signal: AbortSignal }) =>
        (
          await LegalService.readCurrentProvision({
            path: { canonical_path: bookmark.canonical_path },
            query: { release_version: bookmark.release_version },
            signal,
          })
        ).data.data[0],
      retry: false,
    })),
  })
  const visible = bookmarks
    .map((bookmark, index) => ({ bookmark, detail: details[index] }))
    .filter(({ bookmark, detail }) => {
      if (!query.trim() || detail.isPending || detail.isError) return true
      const text =
        `${detail.data?.citation ?? bookmark.canonical_path} ${detail.data?.title ?? ""} ${detail.data?.heading ?? ""} ${detail.data?.authoritative_text ?? ""}`.toLowerCase()
      return text.includes(query.trim().toLowerCase())
    })
  return (
    <section className="mx-auto max-w-5xl px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
      <SectionHeading kicker="Saved" title="Saved sections.">
        Sections you save stay on this device.
      </SectionHeading>
      <div className="mb-5 flex flex-wrap gap-2">
        <InlineAction asChild>
          <Link to="/constitution">Browse sections</Link>
        </InlineAction>
        {bookmarks.length > 0 && (
          <InlineAction
            type="button"
            onClick={() =>
              downloadResearch("constitution-ng-bookmarks.json", {
                format_version: 1,
                exported_at: new Date().toISOString(),
                bookmarks,
                notice:
                  "Bookmarks retain their source edition. Full wording is available through the linked public sections.",
              })
            }
          >
            Export saved sections
          </InlineAction>
        )}
      </div>
      <input
        aria-label="Search saved sections"
        className="sq-md mb-6 min-h-12 w-full max-w-lg border border-border bg-card px-4 text-sm"
        placeholder="Search saved sections"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {storageError && (
        <p className="mb-4 text-sm" role="alert">
          {storageError}
        </p>
      )}
      {bookmarks.length === 0 ? (
        <EmptyState title="Nothing saved yet">
          Tap Save on any section to keep it here for later.
          <div className="mt-4">
            <InlineAction asChild>
              <Link to="/" search={{ intent: "find" }}>
                Find your first section
              </Link>
            </InlineAction>
          </div>
        </EmptyState>
      ) : visible.length === 0 ? (
        <EmptyState title="Nothing matches that search">
          Try a different word or a section number.
        </EmptyState>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {visible.map(({ bookmark, detail }) => (
            <SavedCard
              key={`${bookmark.canonical_path}:${bookmark.release_version}`}
              bookmark={bookmark}
              detail={detail}
            />
          ))}
        </div>
      )}
    </section>
  )
}

function SavedCard({
  bookmark,
  detail,
}: {
  bookmark: Bookmark
  detail: ReturnType<typeof useProvision>
}) {
  const { toggle } = useSavedProvisions()
  const remove = () => {
    try {
      toggle(bookmark.canonical_path, bookmark.release_version)
    } catch {
      toast.error("Your browser could not remove this bookmark.")
    }
  }
  const provision = detail.data
  return (
    <article className="sq-lg grid gap-3 border border-border bg-card p-5">
      {detail.isPending ? (
        <p role="status">Loading…</p>
      ) : detail.isError || !provision ? (
        <p role="alert">
          {legalError(detail.error)} Your bookmark is still saved.
        </p>
      ) : (
        <>
          <StatusBadge
            status={
              provision.legal_status === "current" ? "current" : "historical"
            }
            label={statusLabel(provision.legal_status, provision.edition_label)}
          />
          <h2 className="font-display text-xl">{provisionTitle(provision)}</h2>
          {provision.title && <p className="text-sm">{provision.citation}</p>}
          <EditionNotice
            label={provision.edition_label}
            historical={provision.legal_status === "historical"}
          />
          <Link
            className="text-sm font-semibold text-primary hover:underline"
            to="/constitution/$sectionId"
            params={{ sectionId: bookmark.canonical_path }}
            search={{ release: bookmark.release_version }}
          >
            Open section
          </Link>
        </>
      )}
      <InlineAction onClick={remove} type="button">
        Remove
      </InlineAction>
    </article>
  )
}
