import { useEffect, useState } from "react"
import { FiCheckCircle } from "react-icons/fi"
import type {
  IngestionRunDetail,
  IngestionRunPublic,
  PageInclusionStatus,
  SourcePagePublic,
} from "@/client"
import {
  formatMetric,
  formatPercent,
  labelize,
  shortId,
} from "@/components/Constitution/admin/format"
import {
  FieldLabel,
  ListState,
  Panel,
  SmallStat,
  StatusPill,
  TextBlock,
} from "@/components/Constitution/admin/ui"
import {
  SegmentedControl,
  SquircleButton,
} from "@/components/Constitution/primitives"
import { Input } from "@/components/ui/input"
import { getAccessToken } from "@/lib/session"
import { cn } from "@/lib/utils"

type PageBoundaryDraft = Pick<
  SourcePagePublic,
  "inclusion_reason" | "inclusion_status"
>

const pageInclusionOptions: {
  label: string
  value: PageInclusionStatus
}[] = [
  { label: "Include", value: "included" },
  { label: "Exclude", value: "excluded" },
  { label: "Suggested include", value: "suggested_include" },
  { label: "Suggested exclude", value: "suggested_exclude" },
]

export function PageBoundaryWorkspace({
  selectedRun,
  pages,
  isLoading,
  isMutating,
  onConfirm,
}: {
  selectedRun?: IngestionRunPublic | IngestionRunDetail
  pages: SourcePagePublic[]
  isLoading: boolean
  isMutating: boolean
  onConfirm: (pages: SourcePagePublic[]) => void
}) {
  const importedReview =
    selectedRun?.status === "waiting_for_review" &&
    selectedRun.current_stage === "review" &&
    Boolean(selectedRun.pipeline_config.review_import_complete)
  const canConfirm =
    importedReview ||
    (selectedRun?.status === "waiting_for_input" &&
      selectedRun.current_stage === "awaiting_page_confirmation")
  const [pageDrafts, setPageDrafts] = useState<
    Record<string, PageBoundaryDraft>
  >({})
  const [selectedPageNumber, setSelectedPageNumber] = useState<number | null>(
    null,
  )
  const [rangeFrom, setRangeFrom] = useState("")
  const [rangeTo, setRangeTo] = useState("")
  const [rangeReason, setRangeReason] = useState("")
  const draftedPages = pages.map((page) => ({
    ...page,
    ...pageDrafts[page.id],
  }))

  const applyRange = (status: PageInclusionStatus) => {
    const from = Number.parseInt(rangeFrom, 10)
    const to = Number.parseInt(rangeTo, 10)
    if (!Number.isInteger(from) || !Number.isInteger(to) || from > to) return
    setPageDrafts((current) => {
      const next = { ...current }
      for (const page of pages) {
        if (page.page_number >= from && page.page_number <= to) {
          next[page.id] = {
            inclusion_status: status,
            inclusion_reason:
              rangeReason.trim() ||
              (current[page.id]?.inclusion_reason ??
                page.inclusion_reason ??
                null),
          }
        }
      }
      return next
    })
  }
  const selectedPage =
    draftedPages.find((page) => page.page_number === selectedPageNumber) ??
    draftedPages[0]

  useEffect(() => {
    if (!pages.length) {
      setSelectedPageNumber(null)
      return
    }
    if (!pages.some((page) => page.page_number === selectedPageNumber)) {
      setSelectedPageNumber(pages[0].page_number)
    }
  }, [pages, selectedPageNumber])

  const updateSelectedPage = (draft: Partial<PageBoundaryDraft>) => {
    if (!selectedPage) return
    setPageDrafts((current) => ({
      ...current,
      [selectedPage.id]: {
        ...{
          inclusion_reason: selectedPage.inclusion_reason,
          inclusion_status: selectedPage.inclusion_status,
        },
        ...current[selectedPage.id],
        ...draft,
      },
    }))
  }

  return (
    <Panel
      action={
        <SquircleButton
          disabled={!canConfirm || !pages.length || isMutating}
          loading={isMutating}
          onClick={() => onConfirm(draftedPages)}
          type="button"
        >
          <FiCheckCircle className="size-4" aria-hidden />
          {importedReview
            ? "Confirm reviewed boundaries"
            : "Confirm suggested pages"}
        </SquircleButton>
      }
      title="Page boundaries"
    >
      <ListState
        isEmpty={!selectedRun || !pages.length}
        isLoading={isLoading}
      />
      {selectedRun ? (
        <p className="mb-4 text-sm text-muted-foreground">
          {labelize(selectedRun.current_stage)} · {shortId(selectedRun.id)}
        </p>
      ) : null}
      {selectedRun && !canConfirm ? (
        <p className="mb-4 text-sm text-muted-foreground">
          Page selection is available only while this run is awaiting page
          confirmation.
        </p>
      ) : null}
      <section
        aria-label="Page range selection"
        className="sq-md mb-4 grid gap-3 border border-border bg-card p-4"
      >
        <p className="text-sm font-bold">Apply a page range</p>
        <div className="grid gap-2 sm:grid-cols-[1fr_1fr_2fr_auto_auto]">
          <Input
            aria-label="Range from page"
            inputMode="numeric"
            onChange={(event) => setRangeFrom(event.target.value)}
            placeholder="From"
            value={rangeFrom}
          />
          <Input
            aria-label="Range to page"
            inputMode="numeric"
            onChange={(event) => setRangeTo(event.target.value)}
            placeholder="To"
            value={rangeTo}
          />
          <Input
            aria-label="Range reason"
            onChange={(event) => setRangeReason(event.target.value)}
            placeholder="Reason (e.g. schedules must be included)"
            value={rangeReason}
          />
          <SquircleButton
            onClick={() => applyRange("included")}
            size="sm"
            type="button"
          >
            Include range
          </SquircleButton>
          <SquircleButton
            onClick={() => applyRange("excluded")}
            size="sm"
            type="button"
            variant="outline"
          >
            Exclude range
          </SquircleButton>
        </div>
      </section>
      <ul
        className="grid list-none gap-2 p-0 sm:grid-cols-2 lg:grid-cols-3"
        aria-label="Page filmstrip"
      >
        {draftedPages.map((page) => (
          <li key={page.id}>
            <button
              aria-label={`p.${page.page_number} ${labelize(page.role)} ${labelize(
                page.inclusion_status,
              )}`}
              aria-pressed={selectedPage?.id === page.id}
              className="sq-md grid gap-3 border border-border bg-background p-3 md:grid-cols-[88px_1fr_auto]"
              key={page.id}
              onClick={() => setSelectedPageNumber(page.page_number)}
              type="button"
            >
              <div>
                <PageThumbnail page={page} />
                <p className="font-display text-2xl">p.{page.page_number}</p>
                <p className="text-xs text-muted-foreground">
                  {labelize(page.role)}
                </p>
                <p className="mt-1 break-all text-[11px] text-muted-foreground">
                  {page.thumbnail_key ?? "thumbnail pending"}
                </p>
              </div>
              <div>
                <StatusPill status={page.inclusion_status} />
                <p className="mt-2 text-sm text-muted-foreground">
                  {page.inclusion_reason ?? "No decision reason recorded."}
                </p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>Density {formatPercent(page.text_density)}</span>
                  <span>Columns {formatMetric(page.column_count)}</span>
                  <span>{page.orientation ?? "orientation unknown"}</span>
                </div>
              </div>
            </button>
          </li>
        ))}
      </ul>
      {selectedPage ? (
        <>
          <ProvisionalPagePreview page={selectedPage} />
          <PageBoundaryDecision
            onChange={updateSelectedPage}
            page={selectedPage}
          />
        </>
      ) : null}
    </Panel>
  )
}

function PageBoundaryDecision({
  page,
  onChange,
}: {
  page: SourcePagePublic
  onChange: (draft: Partial<PageBoundaryDraft>) => void
}) {
  return (
    <section
      aria-label={`Boundary decision page ${page.page_number}`}
      className="sq-md mt-4 grid gap-3 border border-border bg-background p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-bold">Boundary decision</p>
        <StatusPill status={page.inclusion_status} />
      </div>
      <SegmentedControl
        ariaLabel={`Page ${page.page_number} inclusion status`}
        onChange={(value) => onChange({ inclusion_status: value })}
        options={pageInclusionOptions}
        value={page.inclusion_status}
      />
      <FieldLabel label="Page inclusion reason">
        <Input
          value={page.inclusion_reason ?? ""}
          onChange={(event) =>
            onChange({ inclusion_reason: event.target.value || null })
          }
        />
      </FieldLabel>
    </section>
  )
}

function ProvisionalPagePreview({ page }: { page: SourcePagePublic }) {
  const previewText = signalString(page.quality_signals, "preview_text")
  const detectedProvisions = signalStringList(
    page.quality_signals,
    "detected_provisions",
  )

  return (
    <section
      aria-label={`Provisional preview page ${page.page_number}`}
      className="sq-md mt-4 border border-border bg-background p-4"
    >
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold">Provisional preview</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Page {page.page_number} ·{" "}
            {page.thumbnail_key ?? "thumbnail pending"}
          </p>
        </div>
        <StatusPill status={page.inclusion_status} />
      </div>
      <PageThumbnail page={page} large />
      <div className="grid gap-3 md:grid-cols-3">
        <SmallStat label="Density" value={formatPercent(page.text_density)} />
        <SmallStat
          label="Image coverage"
          value={formatPercent(page.image_coverage)}
        />
        <SmallStat label="Columns" value={formatMetric(page.column_count)} />
      </div>
      <div className="mt-4">
        <TextBlock title="Page text">
          {previewText ?? "Preview text is still processing."}
        </TextBlock>
      </div>
      {detectedProvisions.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {detectedProvisions.map((provision) => (
            <span
              className="sq-xs bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground"
              key={provision}
            >
              {provision}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function PageThumbnail({
  page,
  large = false,
}: {
  page: SourcePagePublic
  large?: boolean
}) {
  const [objectUrl, setObjectUrl] = useState<string>()

  useEffect(() => {
    if (!page.thumbnail_url) {
      setObjectUrl(undefined)
      return
    }
    let cancelled = false
    let loadedUrl: string | undefined
    const token = getAccessToken()
    fetch(page.thumbnail_url, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load thumbnail")
        return response.blob()
      })
      .then((blob) => {
        loadedUrl = URL.createObjectURL(blob)
        if (!cancelled) setObjectUrl(loadedUrl)
      })
      .catch(() => {
        if (!cancelled) setObjectUrl(undefined)
      })
    return () => {
      cancelled = true
      if (loadedUrl) URL.revokeObjectURL(loadedUrl)
    }
  }, [page.thumbnail_url])

  if (!objectUrl) {
    return (
      <div
        className={cn(
          "grid place-items-center bg-muted text-xs text-muted-foreground",
          large ? "mb-4 aspect-[8.5/11]" : "mb-2 aspect-[4/3]",
        )}
      >
        Thumbnail pending
      </div>
    )
  }
  return (
    <img
      alt={`Page ${page.page_number} thumbnail`}
      className={cn(
        "w-full object-contain",
        large ? "mb-4 max-h-[520px]" : "mb-2 aspect-[4/3]",
      )}
      src={objectUrl}
    />
  )
}

function signalString(
  signals: SourcePagePublic["quality_signals"],
  key: string,
): string | null {
  const value = signals?.[key]
  return typeof value === "string" && value.trim() ? value : null
}

function signalStringList(
  signals: SourcePagePublic["quality_signals"],
  key: string,
): string[] {
  const value = signals?.[key]
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === "string")
}
