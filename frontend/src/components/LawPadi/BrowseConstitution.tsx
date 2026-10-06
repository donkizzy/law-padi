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

export function BrowseConstitution() {
  const root = useProvisionTree()
  const [query, setQuery] = useState("")
  const navigate = useNavigate()
  return (
    <section className="mx-auto max-w-5xl px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
      <SectionHeading
        kicker="Published source navigator"
        title="Browse the Constitution."
      >
        {root.data?.edition_label ??
          "Explore the published hierarchy and its stored English wording."}
      </SectionHeading>
      <form
        className="mb-7 flex gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          if (query.trim())
            void navigate({
              to: "/",
              search: { q: query.trim(), mode: "auto" },
            })
        }}
      >
        <input
          aria-label="Search provisions"
          className="sq-md min-w-0 flex-1 border border-border bg-card px-4 text-sm"
          placeholder="Section 33(2)(a) or a topic"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <SquircleButton type="submit" disabled={!query.trim()}>
          Search
        </SquircleButton>
      </form>
      {root.isPending ? (
        <SkeletonBlock />
      ) : root.isError ? (
        <ErrorState
          title="Corpus unavailable"
          action={
            <InlineAction onClick={() => root.refetch()} type="button">
              Try again
            </InlineAction>
          }
        >
          {legalError(root.error)}
        </ErrorState>
      ) : (
        <div className="grid gap-3">
          {root.data.data.map((node) => (
            <TreeNode
              key={node.id}
              node={node}
              release={root.data.release_version}
            />
          ))}
        </div>
      )}
    </section>
  )
}

function TreeNode({
  node,
  release,
}: {
  node: ProvisionReference
  release: string
}) {
  const [expanded, setExpanded] = useState(false)
  if (
    ["section", "subsection", "paragraph", "schedule_item"].includes(node.kind)
  )
    return (
      <Link
        to="/constitution/$sectionId"
        params={{ sectionId: node.canonical_path }}
        search={{ release }}
        className="sq-md block border border-border bg-card p-4 text-sm hover:border-primary focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="font-bold text-primary">{node.citation}</span>
        <span className="mt-1 block">{node.heading}</span>
      </Link>
    )
  return (
    <section className="sq-lg border border-border bg-card p-4">
      <button
        className="w-full text-left focus-visible:ring-2 focus-visible:ring-ring"
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-xs font-bold text-primary">{node.citation}</span>
        <span className="mt-1 block font-legal text-xl">{node.heading}</span>
      </button>
      {expanded && (
        <TreeChildren parent={node.canonical_path} release={release} />
      )}
    </section>
  )
}

function TreeChildren({
  parent,
  release,
}: {
  parent: string
  release: string
}) {
  const tree = useProvisionTree(parent, release)
  return (
    <div className="mt-4 grid gap-3 border-t border-border pt-4">
      {tree.isPending ? (
        <p role="status">Loading provisions…</p>
      ) : tree.isError ? (
        <ErrorState
          title="Hierarchy unavailable"
          action={
            <InlineAction onClick={() => tree.refetch()} type="button">
              Try again
            </InlineAction>
          }
        >
          {legalError(tree.error)}
        </ErrorState>
      ) : tree.data.data.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No text provisions are stored here.
        </p>
      ) : (
        tree.data.data.map((node) => (
          <TreeNode key={node.id} node={node} release={release} />
        ))
      )}
    </div>
  )
}
