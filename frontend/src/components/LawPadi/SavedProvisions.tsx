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
        `${detail.data?.citation ?? bookmark.canonical_path} ${detail.data?.heading ?? ""} ${detail.data?.authoritative_text ?? ""}`.toLowerCase()
      return text.includes(query.trim().toLowerCase())
    })
  return (
    <section className="mx-auto max-w-5xl px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
      <SectionHeading kicker="Saved research" title="Saved provisions.">
        Bookmarks are kept in this browser and preserve their source edition.
      </SectionHeading>
      <input
        aria-label="Search saved provisions"
        className="sq-md mb-6 min-h-12 w-full max-w-lg border border-border bg-card px-4 text-sm"
        placeholder="Search saved provisions"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {storageError && (
        <p className="mb-4 text-sm" role="alert">
          {storageError}
        </p>
      )}
      {bookmarks.length === 0 ? (
        <EmptyState title="No saved provisions yet">
          Use Save on a provision to keep its wording and source close.
        </EmptyState>
      ) : visible.length === 0 ? (
        <EmptyState title="No saved provision matches">
          Try another citation or topic.
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
        <p role="status">Loading saved wording…</p>
      ) : detail.isError || !provision ? (
        <p role="alert">
          {legalError(detail.error)} Bookmark retained:{" "}
          {bookmark.canonical_path}
        </p>
      ) : (
        <>
          <StatusBadge
            status={
              provision.legal_status === "current" ? "current" : "historical"
            }
          />
          <h2 className="font-legal text-xl">{provision.citation}</h2>
          <p className="text-sm">{provision.heading}</p>
          <p className="text-xs text-muted-foreground">
            {provision.edition_label}
          </p>
          <Link
            className="text-sm font-semibold text-primary hover:underline"
            to="/constitution/$sectionId"
            params={{ sectionId: bookmark.canonical_path }}
            search={{ release: bookmark.release_version }}
          >
            Open provision
          </Link>
        </>
      )}
      <InlineAction onClick={remove} type="button">
        Remove bookmark
      </InlineAction>
    </article>
  )
}
