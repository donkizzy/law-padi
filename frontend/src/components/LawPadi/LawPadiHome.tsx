import { useNavigate, useSearch } from "@tanstack/react-router"
import { AxiosError } from "axios"
import { useState } from "react"
import { ChatComposer } from "@/components/LawPadi/ChatComposer"
import { ChatHome } from "@/components/LawPadi/ChatHome"
import { ProvisionView } from "@/components/LawPadi/ProvisionView"
import {
  ErrorState,
  InlineAction,
  PromptSuggestion,
  SkeletonBlock,
} from "@/components/LawPadi/primitives"
import { SourcePanel } from "@/components/LawPadi/SourcePanel"
import { useConversations } from "@/hooks/useConversations"
import {
  legalError,
  useLegalRelease,
  useLegalSearch,
  useProvision,
} from "@/hooks/useLegalCorpus"
import { bestContainingSource } from "@/lib/source-ranking"

const suggestions = [
  "Section 37",
  "Section 33(2)(a)",
  "Freedom of expression",
  "Presidential qualifications",
  "Privacy",
]

export function LawPadiHome() {
  const conversations = useConversations()
  if (conversations.isSuccess) return <ChatHome />
  if (conversations.isPending)
    return (
      <div className="mx-auto max-w-4xl px-4 py-12">
        <SkeletonBlock />
      </div>
    )
  const disabled =
    conversations.error instanceof AxiosError &&
    conversations.error.response?.status === 503
  return <SearchHome explanationDisabled={disabled} />
}

function SearchHome({ explanationDisabled }: { explanationDisabled: boolean }) {
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
          Find an exact section, subsection or paragraph, or search a topic.
          Stored legal wording is shown in English.
        </p>
        <p
          className="mt-3 sq-md border border-amber-500/40 bg-amber-500/5 p-3 text-sm"
          role="status"
        >
          {explanationDisabled
            ? "AI explanations are not enabled in this deployment. Questions currently show published source wording only."
            : "AI explanations are temporarily unavailable. Questions currently show published source wording only."}
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
  const rankedFirst =
    search.data?.outcome === "matches" ? search.data.data[0] : undefined
  const bestMatch =
    search.data?.outcome === "matches"
      ? bestContainingSource(search.data.data)
      : undefined
  const selected =
    search.data?.data.find((item) => item.canonical_path === selectedPath) ??
    exact ??
    bestMatch
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
                {search.data.outcome === "matches" && selected && (
                  <div className="sq-md border border-primary/30 bg-primary/5 p-4">
                    <h2 className="font-legal text-xl">
                      {selected.canonical_path === bestMatch?.canonical_path
                        ? "Best source answer"
                        : "Selected source answer"}
                    </h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {selected.citation} ·{" "}
                      {selected.canonical_path === bestMatch?.canonical_path &&
                      bestMatch?.canonical_path !== rankedFirst?.canonical_path
                        ? `Includes the highest-ranked passage (${rankedFirst?.citation}) and its section context.`
                        : selected.canonical_path ===
                            rankedFirst?.canonical_path
                          ? "Highest-ranked source passage."
                          : "Selected source passage."}{" "}
                      Retrieval rank is not a legal-confidence percentage.
                    </p>
                  </div>
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
                {search.data.outcome !== "exact" && (
                  <section aria-label="Search matches">
                    <h2 className="mb-4 font-legal text-xl">
                      {search.data.outcome === "ambiguous"
                        ? "Choose the source identity"
                        : "Other source matches"}
                    </h2>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {search.data.data
                        .filter(
                          (match) =>
                            search.data.outcome === "ambiguous" ||
                            match.canonical_path !== selected?.canonical_path,
                        )
                        .map((match) => (
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
                              {match.ancestors
                                .map((a) => a.citation)
                                .join(" · ")}{" "}
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
