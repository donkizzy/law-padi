import { useQueries } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { useState } from "react"
import { Trans, useTranslation } from "react-i18next"
import { toast } from "sonner"
import { LegalService } from "@/client"
import {
  EmptyState,
  InlineAction,
  SectionHeading,
  StatusBadge,
} from "@/components/Constitution/primitives"
import useAuth from "@/hooks/useAuth"
import { legalError, type useProvision } from "@/hooks/useLegalCorpus"
import { type Bookmark, useSavedProvisions } from "@/hooks/useSavedProvisions"
import {
  instrumentSlug,
  provisionTitle,
  statusLabel,
} from "@/lib/legal-provisions"
import { downloadResearch } from "@/lib/research"
import { useSessionStatus } from "@/lib/session"
import { EditionNotice } from "./EditionNotice"

/** Where saved sections live, with a gentle nudge when an account would help. */
function SavedWhere() {
  const { t } = useTranslation(["legal", "common"])
  const { user } = useAuth()
  const status = useSessionStatus()
  if (user?.email_verified_at) return <>{t("saved.followsAccount")}</>
  if (status === "signed-in")
    return (
      <Trans
        components={{
          confirm: (
            <Link
              className="font-semibold text-primary underline"
              to="/settings"
            />
          ),
        }}
        i18nKey="saved.untilConfirmed"
        ns="legal"
      />
    )
  return (
    <Trans
      components={{
        signIn: (
          <Link
            className="font-semibold text-primary underline"
            search={{ redirect: "/saved" }}
            to="/login"
          />
        ),
      }}
      i18nKey="saved.onDevice"
      ns="legal"
    />
  )
}

export function SavedProvisions() {
  const { t } = useTranslation(["legal", "common"])
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
      <SectionHeading kicker={t("saved.kicker")} title={t("saved.title")}>
        <SavedWhere />
      </SectionHeading>
      <div className="mb-5 flex flex-wrap gap-2">
        <InlineAction asChild>
          <Link to="/laws">{t("saved.browse")}</Link>
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
            {t("saved.export")}
          </InlineAction>
        )}
      </div>
      <input
        aria-label={t("saved.search")}
        className="sq-md mb-6 min-h-12 w-full max-w-lg border border-border bg-card px-4 text-sm"
        placeholder={t("saved.search")}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {storageError && (
        <p className="mb-4 text-sm" role="alert">
          {t(`common:${storageError}` as never)}
        </p>
      )}
      {bookmarks.length === 0 ? (
        <EmptyState title={t("saved.emptyTitle")}>
          {t("saved.emptyBody")}
          <div className="mt-4">
            <InlineAction asChild>
              <Link to="/" search={{ intent: "find" }}>
                {t("saved.findFirst")}
              </Link>
            </InlineAction>
          </div>
        </EmptyState>
      ) : visible.length === 0 ? (
        <EmptyState title={t("saved.noMatchTitle")}>
          {t("saved.noMatchBody")}
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
  const { t } = useTranslation(["legal", "common"])
  const { toggle } = useSavedProvisions()
  const remove = () => {
    try {
      toggle(bookmark.canonical_path, bookmark.release_version)
    } catch {
      toast.error(t("saved.removeFailed"))
    }
  }
  const provision = detail.data
  return (
    <article className="sq-lg grid gap-3 border border-border bg-card p-5">
      {detail.isPending ? (
        <p role="status">{t("common:status.loading")}</p>
      ) : detail.isError || !provision ? (
        <p role="alert">
          {legalError(detail.error)} {t("saved.stillSaved")}
        </p>
      ) : (
        <>
          <StatusBadge
            status={
              provision.legal_status === "current" ? "current" : "historical"
            }
            label={statusLabel(
              provision.legal_status,
              provision.edition_label,
              provision,
            )}
          />
          <h2 className="font-display text-xl">{provisionTitle(provision)}</h2>
          {provision.title && <p className="text-sm">{provision.citation}</p>}
          <EditionNotice
            label={provision.edition_label}
            instrument={provision}
            historical={provision.legal_status === "historical"}
          />
          <Link
            className="text-sm font-semibold text-primary hover:underline"
            to="/laws/$instrument/$sectionId"
            params={{
              instrument: instrumentSlug(bookmark),
              sectionId: bookmark.canonical_path,
            }}
            search={{ release: bookmark.release_version }}
          >
            {t("saved.open")}
          </Link>
        </>
      )}
      <InlineAction onClick={remove} type="button">
        {t("common:actions.remove")}
      </InlineAction>
    </article>
  )
}
