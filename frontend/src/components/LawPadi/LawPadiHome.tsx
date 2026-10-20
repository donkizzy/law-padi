import { useNavigate, useSearch } from "@tanstack/react-router"
import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { ChatComposer } from "@/components/LawPadi/ChatComposer"
import { ChatHome } from "@/components/LawPadi/ChatHome"
import { LawPicker } from "@/components/LawPadi/LawPicker"
import { ProvisionView } from "@/components/LawPadi/ProvisionView"
import {
  ErrorState,
  InlineAction,
  PromptSuggestion,
  SkeletonBlock,
} from "@/components/LawPadi/primitives"
import { SourcePanel } from "@/components/LawPadi/SourcePanel"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useChatCapabilities } from "@/hooks/useChatCapabilities"
import { useChatDraft } from "@/hooks/useChatDraft"
import {
  legalError,
  useLegalInstruments,
  useLegalRelease,
  useLegalSearch,
  useProvision,
} from "@/hooks/useLegalCorpus"
import { editionName, pageLabel, sectionQuery } from "@/lib/legal-provisions"
import { serverMessage } from "@/lib/server-messages"
import { bestContainingSource } from "@/lib/source-ranking"
import { EditionNotice } from "./EditionNotice"

export function LawPadiHome() {
  const { t } = useTranslation(["chat", "common"])
  const search = useSearch({ from: "/_layout/" })
  const navigate = useNavigate({ from: "/" })
  const capabilities = useChatCapabilities()
  const intent =
    search.intent ?? (capabilities.data?.conversations_enabled ? "ask" : "find")
  return (
    <div>
      <Tabs
        value={intent}
        onValueChange={(value) =>
          void navigate({
            to: "/",
            search: {
              ...search,
              intent: value as "ask" | "find",
              q: undefined,
              selected: undefined,
            },
          })
        }
        className="block"
      >
        <div className="mx-auto w-full max-w-4xl px-4 pt-5 sm:px-8 lg:px-12">
          <TabsList aria-label={t("tasks.label")} className="sq-md h-11">
            <TabsTrigger value="ask" className="sq-sm min-h-9 px-4">
              {t("common:nav.ask")}
            </TabsTrigger>
            <TabsTrigger value="find" className="sq-sm min-h-9 px-4">
              {t("common:nav.findSection")}
            </TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value={intent}>
          {capabilities.isPending ? (
            <div className="mx-auto max-w-4xl px-4 py-8" role="status">
              <p className="mb-4 text-body text-muted-foreground">
                {t("tasks.checking")}
              </p>
              <SkeletonBlock />
            </div>
          ) : intent === "ask" && capabilities.data?.conversations_enabled ? (
            <ChatHome
              key={
                search.c ??
                `${search.fresh ?? "new"}:${search.q ?? ""}:${search.selected ?? ""}:${search.release ?? ""}`
              }
            />
          ) : (
            <SearchHome
              key={search.fresh ?? "find"}
              availabilityError={capabilities.isError}
              explanationsEnabled={
                capabilities.data?.explanations_enabled === true
              }
              retryAvailability={() => void capabilities.refetch()}
            />
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function SearchHome({
  availabilityError,
  explanationsEnabled,
  retryAvailability,
}: {
  availabilityError: boolean
  explanationsEnabled: boolean
  retryAvailability: () => void
}) {
  const { t } = useTranslation(["chat", "common"])
  const search = useSearch({ from: "/_layout/" })
  const navigate = useNavigate({ from: "/" })
  const [question, setQuestion] = useChatDraft("find")
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const [attempt, setAttempt] = useState(0)
  const release = useLegalRelease()
  const instruments = useLegalInstruments(search.release)
  const selectedLaw = instruments.data?.data.find(
    (item) => item.slug === search.instrument,
  )
  useEffect(() => {
    if (search.q) setQuestion(search.q)
  }, [search.q, setQuestion])
  const submit = (query = question, mode: "auto" | "semantic" = "auto") => {
    if (!query.trim() || query.length > 2000) return
    setAttempt((current) => current + 1)
    void navigate({
      to: "/",
      search: {
        q: mode === "auto" ? sectionQuery(query) : query.trim(),
        mode,
        intent: "find",
        release: search.release,
        instrument: search.instrument,
      },
    })
  }
  return (
    <section className="min-w-0">
      <div className="mx-auto max-w-4xl px-4 py-6 sm:px-8 lg:px-12">
        {!search.q && (
          <>
            <p className="mb-4 text-overline uppercase text-primary">
              {t("home.kicker")}
            </p>
            <h1 className="font-display text-title-1 sm:text-display">
              {t("find.title")}
            </h1>
            <p className="mt-4 max-w-xl text-body-lg text-muted-foreground">
              {t("find.intro")}
            </p>
          </>
        )}
        {(availabilityError || !explanationsEnabled) && (
          <div
            className="mt-4 sq-md border border-border bg-secondary p-3 text-body"
            role="status"
          >
            {availabilityError ? t("find.availabilityError") : t("find.paused")}
            <InlineAction
              className="ml-2"
              type="button"
              onClick={retryAvailability}
            >
              {t("common:actions.checkAgain")}
            </InlineAction>
          </div>
        )}
        <div className="mt-5">
          <LawPicker
            allowAll
            value={search.instrument || ""}
            release={search.release}
            onChange={(instrument) =>
              void navigate({
                to: "/",
                search: {
                  ...search,
                  instrument: instrument || undefined,
                  intent: "find",
                },
              })
            }
          />
        </div>
        <ChatComposer
          autoFocus={Boolean(search.fresh)}
          className="mt-5"
          value={question}
          inputRef={inputRef}
          onChange={setQuestion}
          onSubmit={() => submit()}
          compact={Boolean(search.q)}
          contextLabel={
            selectedLaw
              ? editionName(selectedLaw.edition_label, selectedLaw.slug)
              : instruments.data && instruments.data.count > 1
                ? t("find.allEditions")
                : editionName(release.data?.edition_label)
          }
          placeholder={t("find.placeholder")}
        />
        {!search.q && (
          <fieldset className="mt-4 flex flex-wrap gap-2">
            <legend className="sr-only">{t("find.suggestionsLabel")}</legend>
            {(t("find.suggestions", { returnObjects: true }) as string[]).map(
              (prompt) => (
                <PromptSuggestion
                  key={prompt}
                  onClick={() => {
                    setQuestion(prompt)
                    inputRef.current?.focus()
                  }}
                  type="button"
                >
                  {prompt}
                </PromptSuggestion>
              ),
            )}
          </fieldset>
        )}
        {!search.q && release.isError && (
          <div className="mt-6">
            <ErrorState
              title={t("find.loadFailed")}
              action={
                <InlineAction type="button" onClick={() => release.refetch()}>
                  {t("common:actions.tryAgain")}
                </InlineAction>
              }
            >
              {legalError(release.error)}
            </ErrorState>
          </div>
        )}
        {!search.q && !release.isError && (
          <EditionNotice
            label={selectedLaw?.edition_label || release.data?.edition_label}
            instrument={selectedLaw?.slug}
            historical={
              Boolean(selectedLaw) ||
              !instruments.data ||
              instruments.data.count === 1
            }
            className="mt-6 border-t border-border pt-5"
          />
        )}
      </div>
      {search.q && (
        <SearchResults
          key={`${search.q}:${search.mode}:${search.instrument}:${search.release}:${attempt}`}
          query={search.q}
          mode={search.mode ?? "auto"}
          attempt={attempt}
          release={search.release}
          instrument={search.instrument}
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
  release,
  instrument,
}: {
  query: string
  mode: "auto" | "semantic"
  attempt: number
  onRelated: (query: string) => void
  release?: string
  instrument?: string
}) {
  const { t } = useTranslation(["chat", "common"])
  const resultsRef = useRef<HTMLElement | null>(null)
  const search = useLegalSearch(query, mode, attempt, release, instrument)
  useEffect(() => {
    if (search.isPending) return
    const frame = requestAnimationFrame(() => {
      const active = document.activeElement
      if (
        active instanceof HTMLTextAreaElement &&
        active.value.trim() !== query
      )
        return
      resultsRef.current?.focus({ preventScroll: true })
      resultsRef.current?.scrollIntoView({ block: "start" })
    })
    return () => cancelAnimationFrame(frame)
  }, [search.isPending, query])
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
      <section
        ref={resultsRef}
        tabIndex={-1}
        aria-label={t("results.label")}
        className="mx-auto grid w-full max-w-4xl scroll-mt-20 gap-6 px-4 pb-12 outline-none sm:px-8 lg:px-12"
      >
        <p className="border-t border-border pt-7 text-body font-semibold">
          {t("results.title", { query })}
        </p>
        {search.isPending ? (
          <div role="status">
            <p className="mb-4 text-sm text-muted-foreground">
              {t("results.searching")}
            </p>
            <SkeletonBlock />
          </div>
        ) : search.isError ? (
          <ErrorState
            title={t("results.unavailable")}
            action={
              <InlineAction onClick={() => search.refetch()} type="button">
                {t("common:actions.tryAgain")}
              </InlineAction>
            }
          >
            {legalError(search.error)}
          </ErrorState>
        ) : (
          <>
            {search.data.searched_query && (
              <p className="text-sm text-muted-foreground">
                {t("results.searchedFor", {
                  query: search.data.searched_query,
                })}
              </p>
            )}
            {search.data.message && (
              <p role="status" className="sq-md bg-secondary p-4 text-sm">
                {serverMessage(search.data.message, search.data.message_code)}
              </p>
            )}
            {search.data.data.length === 0 ? (
              <ErrorState
                title={
                  search.data.outcome === "unsupported_reference"
                    ? t("results.unsupported")
                    : t("results.none")
                }
              >
                {t("results.noneHint")}
              </ErrorState>
            ) : (
              <>
                {search.data.outcome === "matches" && selected && (
                  <div className="sq-md border border-primary/30 bg-primary/5 p-4">
                    <h2 className="font-display text-xl">
                      {selected.canonical_path === bestMatch?.canonical_path
                        ? t("results.bestMatch")
                        : t("results.selected")}
                    </h2>
                    <p className="mt-1 text-body text-muted-foreground">
                      {selected.citation}
                      {selected.title ? ` · ${selected.title}` : ""}
                      {selected.canonical_path === bestMatch?.canonical_path &&
                      bestMatch?.canonical_path !== rankedFirst?.canonical_path
                        ? t("results.inContext", {
                            citation: rankedFirst?.citation,
                          })
                        : ""}
                    </p>
                  </div>
                )}
                {provision && (
                  <>
                    {detail.isError && (
                      <p role="alert" className="text-sm">
                        {legalError(detail.error)}{" "}
                        {t("results.surroundingFailed")}
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
                  <section aria-label={t("results.matchesLabel")}>
                    <h2 className="mb-4 font-display text-xl">
                      {search.data.outcome === "ambiguous"
                        ? t("results.ambiguous")
                        : t("results.otherMatches")}
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
                              {match.title || match.heading || match.citation}
                            </span>
                            <span className="mt-2 block text-xs text-muted-foreground">
                              {[
                                ...match.ancestors.map((a) => a.citation),
                                match.source_page_start
                                  ? pageLabel(match.source_page_start)
                                  : null,
                              ]
                                .filter(Boolean)
                                .join(" · ")}
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
      </section>
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
