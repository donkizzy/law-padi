import { Link, useNavigate } from "@tanstack/react-router"
import { useState } from "react"
import type { ProvisionReference } from "@/client"
import {
  ErrorState,
  InlineAction,
  SectionHeading,
  SkeletonBlock,
  SquircleButton,
} from "@/components/LawPadi/primitives"
import { legalError, useProvisionTree } from "@/hooks/useLegalCorpus"
import { editionName } from "@/lib/legal-provisions"

export function BrowseConstitution({
  parent,
  release,
}: {
  parent?: string
  release?: string
}) {
  const root = useProvisionTree(parent, release)
  const [query, setQuery] = useState("")
  const navigate = useNavigate()
  return (
    <section className="mx-auto max-w-5xl px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
      <SectionHeading
        kicker="Browse"
        title={
          root.data?.parent
            ? `${root.data.parent.citation}: ${root.data.parent.title || root.data.parent.heading || "Published provisions"}`
            : "Browse the Constitution."
        }
      >
        Explore the available chapters and sections of the{" "}
        {editionName(root.data?.edition_label)}. Later amendments are not
        included.
      </SectionHeading>
      {parent && (
        <Link
          className="mb-5 inline-block text-primary underline"
          to="/constitution"
          search={{ release: root.data?.release_version ?? release }}
        >
          All chapters and schedules
        </Link>
      )}
      <form
        className="mb-7 flex gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          if (query.trim())
            void navigate({
              to: "/",
              search: { q: query.trim(), mode: "auto", intent: "find" },
            })
        }}
      >
        <input
          aria-label="Search the Constitution"
          className="sq-md min-w-0 flex-1 border border-border bg-card px-4 text-sm"
          placeholder="Search a topic or a section number"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          maxLength={2000}
        />
        <SquircleButton type="submit" disabled={!query.trim()}>
          Search
        </SquircleButton>
      </form>
      {root.isPending ? (
        <SkeletonBlock />
      ) : root.isError ? (
        <ErrorState
          title="Couldn't load the Constitution"
          action={
            <InlineAction onClick={() => root.refetch()} type="button">
              Try again
            </InlineAction>
          }
        >
          {legalError(root.error)}
        </ErrorState>
      ) : (
        <ul className="grid gap-3">
          {root.data.data.map((node) => (
            <li key={node.id}>
              <ReadingLink node={node} release={root.data.release_version} />
            </li>
          ))}
        </ul>
      )}
      <Link
        className="mt-8 inline-block text-sm text-primary underline"
        to="/about"
      >
        Sources, edition limits and corrections
      </Link>
    </section>
  )
}

function ReadingLink({
  node,
  release,
}: {
  node: ProvisionReference
  release: string
}) {
  const document = node.has_text
  const contents = (
    <>
      <span className="font-bold text-primary">{node.citation}</span>
      <span className="mt-1 block">
        {node.title || node.heading || "Read published provisions"}
      </span>
    </>
  )
  const className =
    "sq-md block border border-border bg-card p-4 text-sm hover:border-primary focus-visible:ring-2 focus-visible:ring-ring"
  return document ? (
    <Link
      to="/constitution/$sectionId"
      params={{ sectionId: node.canonical_path }}
      search={{ release }}
      className={className}
    >
      {contents}
    </Link>
  ) : (
    <Link
      to="/constitution"
      search={{ parent: node.canonical_path, release }}
      className={className}
    >
      {contents}
    </Link>
  )
}
