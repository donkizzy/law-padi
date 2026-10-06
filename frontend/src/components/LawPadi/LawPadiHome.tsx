import { useNavigate, useSearch } from "@tanstack/react-router"
import { useState } from "react"
import { ChatComposer } from "@/components/LawPadi/ChatComposer"
import { ProvisionView } from "@/components/LawPadi/ProvisionView"
import {
  ErrorState,
  InlineAction,
  PromptSuggestion,
  SkeletonBlock,
} from "@/components/LawPadi/primitives"
import { SourcePanel } from "@/components/LawPadi/SourcePanel"
import {
  legalError,
  useLegalRelease,
  useLegalSearch,
  useProvision,
} from "@/hooks/useLegalCorpus"

const suggestions = [
  "Section 37",
  "Section 33(2)(a)",
  "Freedom of expression",
  "Presidential qualifications",
  "Privacy",
]

export function LawPadiHome() {
  const search = useSearch({ from: "/_layout/" })
  const navigate = useNavigate({ from: "/" })
  const [question, setQuestion] = useState("")
  const [attempt, setAttempt] = useState(0)
  const release = useLegalRelease()
  const submit = (query = question, mode: "auto" | "semantic" = "auto") => {
    if (!query.trim()) return
    setQuestion("")
    setAttempt((current) => current + 1)
    void navigate({ to: "/", search: { q: query.trim(), mode } })
  }
  return (
    <section className="min-w-0">
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
        <p className="mb-5 text-xs font-bold uppercase text-primary">
          The law, made understandable
        </p>
        <h1 className="font-legal text-[2.35rem] leading-[1.03] sm:text-[3.35rem]">
          Explore Nigeria&apos;s Constitution.
        </h1>
        <p className="mt-4 text-sm leading-7 text-muted-foreground">
          Find an exact section, subsection or paragraph, or search a topic and
          choose a source match. Stored legal wording is shown in English.
        </p>
        <p className="mt-3 text-xs font-semibold text-muted-foreground">
          {release.data?.edition_label ?? "Published source edition"}
        </p>
        <ChatComposer
          className="mt-8"
          value={question}
          onChange={setQuestion}
          onSubmit={() => submit()}
        />
        <fieldset className="mt-5 flex flex-wrap gap-2">
          <legend className="sr-only">Suggested searches</legend>
          {suggestions.map((prompt) => (
            <PromptSuggestion
              key={prompt}
              onClick={() => setQuestion(prompt)}
              type="button"
            >
              {prompt}
            </PromptSuggestion>
          ))}
        </fieldset>
        {!search.q && release.isError && (
          <div className="mt-8">
            <ErrorState
              title="Corpus unavailable"
              action={
                <InlineAction type="button" onClick={() => release.refetch()}>
                  Try again
                </InlineAction>
              }
            >
              {legalError(release.error)}
            </ErrorState>
          </div>
        )}
        {!search.q && !release.isError && (
          <p className="mt-10 border-t border-border pt-7 text-sm text-muted-foreground">
            Start with a reference such as Section 33(2)(a), or a topic such as
            privacy. This edition is historical; its publication does not
            certify current consolidated law.
          </p>
        )}
      </div>
      {search.q && (
        <SearchResults
          key={`${search.q}:${search.mode}:${attempt}`}
          query={search.q}
          mode={search.mode ?? "auto"}
          attempt={attempt}
          onRelated={(query) => submit(query, "semantic")}
        />
      )}
    </section>
  )
}

function SearchResults({
  query,
  mode,
  attempt,
  onRelated,
}: {
  query: string
  mode: "auto" | "semantic"
  attempt: number
  onRelated: (query: string) => void
}) {
  const search = useLegalSearch(query, mode, attempt)
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [sourceOpen, setSourceOpen] = useState(false)
  const exact =
    search.data?.outcome === "exact" ? search.data.data[0] : undefined
  const selected =
    search.data?.data.find((item) => item.canonical_path === selectedPath) ??
    exact
  const detail = useProvision(
    selected?.canonical_path ?? "",
    selected?.release_version,
  )
  const provision = detail.data ?? selected
  return (
    <div
      className={
        sourceOpen && provision
          ? "grid xl:grid-cols-[minmax(0,1fr)_380px]"
          : "grid"
      }
    >
      <div className="mx-auto grid w-full max-w-4xl gap-6 px-4 pb-12 sm:px-8 lg:px-12">
        <p className="border-t border-border pt-7 text-sm font-semibold">
          Search: {query}
        </p>
        {search.isPending ? (
          <div role="status">
            <p className="mb-4 text-sm text-muted-foreground">
              Searching the published source…
            </p>
            <SkeletonBlock />
          </div>
        ) : search.isError ? (
          <ErrorState
            title="Search unavailable"
            action={
              <InlineAction onClick={() => search.refetch()} type="button">
                Try again
              </InlineAction>
            }
          >
            {legalError(search.error)}
          </ErrorState>
        ) : (
          <>
            {search.data.message && (
              <p role="status" className="sq-md bg-secondary p-4 text-sm">
                {search.data.message}
              </p>
            )}
            {search.data.data.length === 0 ? (
              <ErrorState
                title={
                  search.data.outcome === "unsupported_reference"
                    ? "Reference not supported"
                    : "No matching provision found"
                }
              >
                Try Section 33(2)(a), another section number, or a broader
                topic.
              </ErrorState>
            ) : (
              <>
                {search.data.outcome !== "exact" && (
                  <section aria-label="Search matches">
                    <h2 className="mb-4 font-legal text-xl">
                      {search.data.outcome === "ambiguous"
                        ? "Choose the source identity"
                        : "Possible source matches"}
                    </h2>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {search.data.data.map((match) => (
                        <button
                          key={match.provision_version_id}
                          type="button"
                          aria-pressed={
                            selected?.canonical_path === match.canonical_path
                          }
                          onClick={() => {
                            setSelectedPath(match.canonical_path)
                            setSourceOpen(false)
                          }}
                          className="sq-md border border-border bg-card p-4 text-left hover:border-primary focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <span className="text-sm font-bold text-primary">
                            {match.citation}
                          </span>
                          <span className="mt-2 block text-sm font-semibold">
                            {match.heading || match.citation}
                          </span>
                          <span className="mt-2 block text-xs text-muted-foreground">
                            {match.ancestors.map((a) => a.citation).join(" · ")}{" "}
                            · PDF page{" "}
                            {match.source_page_start ?? "not recorded"}
                          </span>
                          <span className="mt-2 block text-xs text-muted-foreground">
                            {match.legal_status} · {match.edition_label}
                          </span>
                        </button>
                      ))}
                    </div>
                  </section>
                )}
                {provision && (
                  <>
                    {detail.isError && (
                      <p role="alert" className="text-sm">
                        {legalError(detail.error)} Parent context could not be
                        loaded.
                      </p>
                    )}
                    <ProvisionView
                      key={provision.provision_version_id}
                      provision={provision}
                      onOpenSource={() => setSourceOpen(true)}
                      onRelated={onRelated}
                    />
                  </>
                )}
              </>
            )}
          </>
        )}
      </div>
      {provision && (
        <SourcePanel
          open={sourceOpen}
          onOpenChange={setSourceOpen}
          provision={provision}
        />
      )}
    </div>
  )
}
