import { Link, useNavigate } from "@tanstack/react-router"
import { useState } from "react"
import type { ProvisionReference } from "@/client"
import { LawPicker } from "@/components/LawPadi/LawPicker"
import {
  ErrorState,
  InlineAction,
  SectionHeading,
  SkeletonBlock,
  SquircleButton,
} from "@/components/LawPadi/primitives"
import {
  legalError,
  useLegalInstruments,
  useProvisionTree,
} from "@/hooks/useLegalCorpus"
import {
  editionName,
  instrumentSlug,
  lawName,
  sectionQuery,
} from "@/lib/legal-provisions"
import { EditionNotice } from "./EditionNotice"

export function BrowseConstitution({
  parent,
  release,
  instrument = "constitution-1999",
}: {
  parent?: string
  release?: string
  instrument?: string
}) {
  const root = useProvisionTree(parent, release, instrument)
  const edition = root.data?.release_version ?? release
  const instruments = useLegalInstruments(edition)
  const selected = instruments.data?.data.find(
    (item) => item.slug === instrument,
  )
  const [query, setQuery] = useState("")
  const navigate = useNavigate()
  return (
    <section className="mx-auto max-w-5xl px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
      <SectionHeading
        kicker="Browse"
        title={
          root.data?.parent
            ? `${root.data.parent.citation}: ${root.data.parent.title || root.data.parent.heading || "Published provisions"}`
            : `Browse ${selected?.short_title || selected?.title || lawName(instrument)}.`
        }
      >
        Explore the available parts and sections of{" "}
        {editionName(root.data?.edition_label, instrument)}.
      </SectionHeading>
      <LawPicker
        value={instrument}
        release={edition}
        onChange={(slug) =>
          void navigate({
            to: "/laws/$instrument",
            params: { instrument: slug },
            search: { release: edition },
          })
        }
      />
      <EditionNotice
        label={selected?.edition_label || root.data?.edition_label}
        instrument={instrument}
        className="mb-6"
      />
      {selected && (
        <p className="mb-5 text-label font-normal text-muted-foreground">
          {selected.section_count} published sections · {selected.edition_note}
        </p>
      )}
      {parent && (
        <Link
          className="mb-5 inline-block text-primary underline"
          to="/laws/$instrument"
          params={{ instrument }}
          search={{ release: edition }}
        >
          All parts and sections
        </Link>
      )}
      <form
        className="mb-7 flex gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          if (query.trim())
            void navigate({
              to: "/",
              search: {
                q: sectionQuery(query),
                mode: "auto",
                intent: "find",
                instrument,
                release: edition,
              },
            })
        }}
      >
        <input
          aria-label="Search this law"
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
          title="Couldn't load this law"
          action={
            <InlineAction onClick={() => root.refetch()} type="button">
              Try again
            </InlineAction>
          }
        >
          {legalError(root.error)}
        </ErrorState>
      ) : root.data.data.length ? (
        <ul className="grid gap-3">
          {root.data.data.map((node) => (
            <li key={node.id}>
              <ReadingLink node={node} release={root.data.release_version} />
            </li>
          ))}
        </ul>
      ) : (
        <p>No sections are available at this level in this edition.</p>
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
  const instrument = instrumentSlug(node)
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
  return node.has_text ? (
    <Link
      to="/laws/$instrument/$sectionId"
      params={{ instrument, sectionId: node.canonical_path }}
      search={{ release }}
      className={className}
    >
      {contents}
    </Link>
  ) : (
    <Link
      to="/laws/$instrument"
      params={{ instrument }}
      search={{ parent: node.canonical_path, release }}
      className={className}
    >
      {contents}
    </Link>
  )
}
