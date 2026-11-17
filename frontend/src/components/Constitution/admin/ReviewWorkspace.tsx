import { useEffect, useState } from "react"
import {
  FiCheckCircle,
  FiFileText,
  FiRefreshCcw,
  FiXCircle,
} from "react-icons/fi"
import type {
  ExtractionCandidateStatus,
  ReviewDecisionCreate,
  ReviewDecisionType,
  ReviewItemPublic,
  ReviewItemUpdate,
  SourceDocumentPublic,
  SourcePagePublic,
} from "@/client"
import { CandidateStructureEditor } from "@/components/Constitution/admin/CandidateStructureEditor"
import { DeriveProvisionForm } from "@/components/Constitution/admin/DeriveProvisionForm"
import { formatPercent, labelize } from "@/components/Constitution/admin/format"
import { ResolveReviewIssueForm } from "@/components/Constitution/admin/ResolveReviewIssueForm"
import {
  sourceBoxStyle,
  sourceSpanPreviews,
} from "@/components/Constitution/admin/source-spans"
import {
  EmptyState,
  FieldLabel,
  inputClass,
  ListState,
  Panel,
  SmallStat,
  StatusPill,
  TextBlock,
} from "@/components/Constitution/admin/ui"
import { SquircleButton } from "@/components/Constitution/primitives"
import { Input } from "@/components/ui/input"
import { getAccessToken } from "@/lib/session"
import { cn } from "@/lib/utils"

export function ReviewWorkspace({
  reviews,
  pages,
  totalCount,
  pageOffset,
  onPageChange,
  statusFilter,
  onStatusFilterChange,
  selected,
  selectedId,
  isLoading,
  isMutating,
  canReview = true,
  canOverride = false,
  onSelect,
  onSave,
  onDecide,
  onVerifySource,
  onDerivedCreated,
  filter,
  onFilter,
}: {
  reviews: ReviewItemPublic[]
  pages: SourcePagePublic[]
  totalCount: number
  pageOffset: number
  onPageChange: (offset: number) => void
  statusFilter: ExtractionCandidateStatus
  onStatusFilterChange: (status: ExtractionCandidateStatus) => void
  selected?: ReviewItemPublic
  selectedId?: string
  isLoading: boolean
  isMutating: boolean
  canReview?: boolean
  canOverride?: boolean
  onSelect: (id: string) => void
  onSave: (id: string, body: ReviewItemUpdate) => void
  onDecide: (id: string, body: ReviewDecisionCreate) => void
  onVerifySource: (source: SourceDocumentPublic, reason: string) => void
  onDerivedCreated: (id: string) => void
  filter: { path: string; page: string }
  onFilter: (filter: { path: string; page: string }) => void
}) {
  const [revisedText, setRevisedText] = useState("")
  const [reason, setReason] = useState("")
  const [decisionReason, setDecisionReason] = useState("")
  const [sourceVerificationReason, setSourceVerificationReason] = useState("")
  const [selectedSpanIndex, setSelectedSpanIndex] = useState(0)
  const [structurePatch, setStructurePatch] = useState<
    Partial<ReviewItemUpdate>
  >({})
  const [structureError, setStructureError] = useState<string>()
  const [pathFilter, setPathFilter] = useState(filter.path)
  const [pageFilter, setPageFilter] = useState(filter.page)

  useEffect(() => {
    setRevisedText(
      selected?.id && selected.lock_version
        ? (selected.latest_revision_text ?? selected.raw_text ?? "")
        : "",
    )
    setReason("")
    setDecisionReason("")
    setSourceVerificationReason("")
    setSelectedSpanIndex(0)
    setStructurePatch({})
    setStructureError(undefined)
  }, [
    selected?.id,
    selected?.lock_version,
    selected?.latest_revision_text,
    selected?.raw_text,
  ])

  const selectedText =
    selected?.latest_revision_text ?? selected?.raw_text ?? ""
  const selectedSource = selected?.source_document
  const sourceVerified = selectedSource?.verification_status === "verified"

  const submitDecision = (decision: ReviewDecisionType) => {
    if (!selected || !decisionReason.trim()) return
    onDecide(selected.id, {
      idempotency_key: `review-decision-${crypto.randomUUID()}`,
      expected_version: selected.lock_version,
      decision,
      reason: decisionReason.trim(),
    })
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
      <Panel title="Review queue" count={totalCount}>
        <form
          className="mb-3 grid gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            onFilter({ path: pathFilter.trim(), page: pageFilter })
          }}
        >
          <Input
            aria-label="Filter canonical path"
            placeholder="Find a provision path"
            value={pathFilter}
            onChange={(event) => setPathFilter(event.target.value)}
          />
          <Input
            aria-label="Filter source page"
            type="number"
            min={1}
            placeholder="Source page"
            value={pageFilter}
            onChange={(event) => setPageFilter(event.target.value)}
          />
          <SquircleButton type="submit" variant="outline">
            Filter reviews
          </SquircleButton>
        </form>
        <label className="mb-3 grid gap-1 text-sm">
          Candidate status
          <select
            className={inputClass}
            value={statusFilter}
            onChange={(event) =>
              onStatusFilterChange(
                event.target.value as ExtractionCandidateStatus,
              )
            }
          >
            {[
              "needs_review",
              "needs_correction",
              "approved",
              "auto_approved",
              "rejected",
              "materialized",
            ].map((status) => (
              <option key={status} value={status}>
                {labelize(status)}
              </option>
            ))}
          </select>
        </label>
        <div className="mb-3 flex items-center justify-between gap-2 text-sm">
          <SquircleButton
            disabled={isLoading || pageOffset === 0}
            onClick={() => onPageChange(Math.max(0, pageOffset - 100))}
            type="button"
            variant="outline"
          >
            Previous
          </SquircleButton>
          <span>
            {totalCount === 0 ? 0 : pageOffset + 1}–
            {Math.min(pageOffset + reviews.length, totalCount)} of {totalCount}
          </span>
          <SquircleButton
            disabled={isLoading || pageOffset + 100 >= totalCount}
            onClick={() => onPageChange(pageOffset + 100)}
            type="button"
            variant="outline"
          >
            Next
          </SquircleButton>
        </div>
        <ListState isLoading={isLoading} isEmpty={!reviews.length} />
        <div className="grid gap-2">
          {reviews.map((item) => (
            <button
              className={cn(
                "sq-md border p-3 text-left transition",
                item.id === selectedId
                  ? "border-primary bg-accent"
                  : "border-border bg-card hover:border-primary/30",
              )}
              key={item.id}
              onClick={() => onSelect(item.id)}
              type="button"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold">
                    {item.heading ?? item.canonical_path}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {item.number
                      ? `${labelize(item.kind)} ${item.number}`
                      : labelize(item.kind)}
                  </p>
                </div>
                <StatusPill status={item.status} />
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {item.blocking_issue_count} blocking · parser{" "}
                {formatPercent(item.parser_confidence)}
              </p>
            </button>
          ))}
        </div>
      </Panel>

      <Panel title="Candidate review">
        {selected ? (
          <div className="grid gap-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xl font-bold">
                  {selected.heading ?? selected.canonical_path}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {selected.canonical_path}
                </p>
              </div>
              <StatusPill status={selected.status} />
            </div>
            <p className="break-all text-xs text-muted-foreground">
              Candidate ID: {selected.id}
            </p>
            <DeriveProvisionForm
              candidate={selected}
              disabled={
                !canReview || isMutating || selected.status === "materialized"
              }
              onCreated={onDerivedCreated}
            />

            <div className="grid gap-3 md:grid-cols-4">
              <SmallStat label="Kind" value={labelize(selected.kind)} />
              <SmallStat
                label="Pages"
                value={
                  selected.source_page_start
                    ? `${selected.source_page_start}-${selected.source_page_end ?? selected.source_page_start}`
                    : "Unknown"
                }
              />
              <SmallStat
                label="Parser"
                value={formatPercent(selected.parser_confidence)}
              />
              <SmallStat
                label="Extractor"
                value={formatPercent(selected.extractor_confidence)}
              />
            </div>

            {!canReview ? (
              <p
                className="sq-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm"
                role="note"
              >
                Read-only: your account lacks the legal_reviewer role.
              </p>
            ) : null}
            <div className="grid gap-4 lg:grid-cols-2">
              <TextBlock title="Raw extraction">{selected.raw_text}</TextBlock>
              <TextBlock title="Current revision">{selectedText}</TextBlock>
            </div>
            <RevisionDiff
              before={selected.raw_text ?? ""}
              after={selectedText}
            />
            {selected.revisions?.length || selected.decisions?.length ? (
              <details className="sq-md min-w-0 border border-border p-3 text-sm">
                <summary className="cursor-pointer font-bold">
                  Review audit history
                </summary>
                {selected.revisions?.map((revision) => (
                  <p key={revision.id} className="mt-3 break-words">
                    Revision {revision.revision_number}: {revision.reason}
                  </p>
                ))}
                {selected.decisions?.map((decision) => (
                  <p key={decision.id} className="mt-3 break-words">
                    {labelize(decision.decision)}: {decision.reason}
                  </p>
                ))}
              </details>
            ) : null}

            <SourceEvidencePreview
              candidate={selected}
              pages={pages}
              onSelect={setSelectedSpanIndex}
              selectedSpanIndex={selectedSpanIndex}
            />

            {selectedSource ? (
              <section
                aria-label="Source document verification"
                className="sq-md grid gap-3 border border-border bg-card p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-bold">Source verification</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {selectedSource.title} · {selectedSource.authority}
                    </p>
                  </div>
                  <StatusPill status={selectedSource.verification_status} />
                </div>
                <div className="grid gap-3 md:grid-cols-[1fr_auto]">
                  <Input
                    aria-label="Source verification reason"
                    className={inputClass}
                    disabled={isMutating || sourceVerified}
                    onChange={(event) =>
                      setSourceVerificationReason(event.target.value)
                    }
                    placeholder="Verification reason"
                    value={sourceVerificationReason}
                  />
                  <SquircleButton
                    disabled={
                      isMutating ||
                      sourceVerified ||
                      !sourceVerificationReason.trim()
                    }
                    onClick={() =>
                      onVerifySource(
                        selectedSource,
                        sourceVerificationReason.trim(),
                      )
                    }
                    size="sm"
                    type="button"
                  >
                    <FiCheckCircle className="size-4" aria-hidden />
                    Verify source
                  </SquircleButton>
                </div>
              </section>
            ) : null}

            {selected.issues?.length ? (
              <div className="grid gap-2">
                {selected.issues.map((issue) => (
                  <div
                    className="sq-md border border-border bg-background p-3"
                    key={issue.id}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold">
                        {labelize(issue.issue_type)}
                      </p>
                      <StatusPill status={issue.status} />
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {issue.message}
                    </p>
                    {issue.evidence ? (
                      <details className="mt-2 text-xs">
                        <summary className="cursor-pointer">
                          Finding evidence
                        </summary>
                        <pre className="mt-2 overflow-auto whitespace-pre-wrap break-words">
                          {JSON.stringify(issue.evidence, null, 2)}
                        </pre>
                      </details>
                    ) : null}
                    {issue.resolution_reason ? (
                      <p className="mt-2 text-sm">{issue.resolution_reason}</p>
                    ) : null}
                    <ResolveReviewIssueForm
                      issue={issue}
                      candidateVersion={selected.lock_version}
                      canOverride={canOverride}
                      disabled={
                        isMutating ||
                        !canReview ||
                        selected.status === "materialized"
                      }
                    />
                  </div>
                ))}
              </div>
            ) : null}

            <CandidateStructureEditor
              key={`${selected.id}-${selected.lock_version}`}
              candidate={selected}
              disabled={
                isMutating || !canReview || selected.status === "materialized"
              }
              onChange={(patch, error) => {
                setStructurePatch(patch)
                setStructureError(error)
              }}
            />
            <FieldLabel label="Revised text">
              <textarea
                className={cn(inputClass, "min-h-36 resize-y py-3")}
                value={revisedText}
                onChange={(event) => setRevisedText(event.target.value)}
              />
            </FieldLabel>
            <FieldLabel label="Revision reason">
              <Input
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </FieldLabel>
            <div className="flex flex-wrap gap-2">
              <SquircleButton
                disabled={
                  isMutating ||
                  !canReview ||
                  selected.status === "materialized" ||
                  Boolean(structureError) ||
                  !reason.trim() ||
                  (!revisedText.trim() &&
                    (Boolean(selectedText.trim()) ||
                      Object.keys(structurePatch).length === 0))
                }
                loading={isMutating}
                onClick={() =>
                  onSave(selected.id, {
                    ...structurePatch,
                    idempotency_key: `review-revision-${crypto.randomUUID()}`,
                    expected_version: selected.lock_version,
                    ...(revisedText.trim()
                      ? { revised_text: revisedText.trim() }
                      : {}),
                    reason: reason.trim(),
                  })
                }
                type="button"
              >
                <FiFileText className="size-4" aria-hidden />
                Save revision
              </SquircleButton>
            </div>

            <FieldLabel label="Decision reason">
              <Input
                value={decisionReason}
                onChange={(event) => setDecisionReason(event.target.value)}
              />
            </FieldLabel>
            <div className="flex flex-wrap gap-2">
              <SquircleButton
                disabled={isMutating || !canReview || !decisionReason.trim()}
                onClick={() => submitDecision("approve")}
                type="button"
              >
                <FiCheckCircle className="size-4" aria-hidden />
                Approve
              </SquircleButton>
              <SquircleButton
                disabled={isMutating || !canReview || !decisionReason.trim()}
                onClick={() => submitDecision("request_correction")}
                type="button"
                variant="outline"
              >
                <FiRefreshCcw className="size-4" aria-hidden />
                Request correction
              </SquircleButton>
              <SquircleButton
                disabled={isMutating || !canReview || !decisionReason.trim()}
                onClick={() => submitDecision("reject")}
                type="button"
                variant="danger"
              >
                <FiXCircle className="size-4" aria-hidden />
                Reject
              </SquircleButton>
            </div>
          </div>
        ) : (
          <EmptyState text="No review item selected." />
        )}
      </Panel>
    </div>
  )
}

function SourceEvidencePreview({
  candidate,
  pages,
  selectedSpanIndex,
  onSelect,
}: {
  candidate: ReviewItemPublic
  pages: SourcePagePublic[]
  selectedSpanIndex: number
  onSelect: (index: number) => void
}) {
  const spans = sourceSpanPreviews(candidate.source_spans, pages)
  const selectedSpan = spans[selectedSpanIndex] ?? spans[0]
  const previewPageNumber = selectedSpan?.page ?? candidate.source_page_start
  const previewPage = pages.find(
    (page) => page.page_number === previewPageNumber,
  )
  const previewUrl =
    previewPage?.thumbnail_url ?? candidate.source_page_thumbnail_url

  return (
    <section
      aria-label="Source preview"
      className="sq-md border border-border bg-background p-4"
    >
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold">Source preview</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {candidate.extractor_version ?? "extractor pending"} ·{" "}
            {candidate.parser_version ?? "parser pending"}
          </p>
        </div>
        <StatusPill status={candidate.status} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(220px,320px)_1fr]">
        <div className="relative aspect-[8.5/11] overflow-hidden border border-border bg-muted">
          {previewUrl ? (
            <ProtectedImage
              alt={`Source page ${previewPageNumber ?? ""}`}
              className="absolute inset-0 h-full w-full object-contain"
              url={previewUrl}
            />
          ) : null}
          {spans.length ? (
            spans.map((span, index) =>
              span.page === previewPageNumber &&
              span.bbox &&
              span.width > 0 &&
              span.height > 0 ? (
                <button
                  aria-label={`Source span page ${span.page ?? "unknown"} box ${
                    index + 1
                  }`}
                  className={cn(
                    "absolute border-2 bg-primary/15 transition",
                    index === selectedSpanIndex
                      ? "border-primary"
                      : "border-[color:var(--legal-gold)]",
                  )}
                  key={`${span.page ?? "unknown"}-${index}`}
                  onClick={() => onSelect(index)}
                  style={sourceBoxStyle(span)}
                  type="button"
                />
              ) : null,
            )
          ) : (
            <div className="grid h-full place-items-center px-4 text-center text-sm text-muted-foreground">
              Source boxes pending.
            </div>
          )}
        </div>
        <div>
          <label className="mb-3 grid gap-1 text-sm">
            Source span
            <select
              className={inputClass}
              value={selectedSpanIndex}
              onChange={(event) => onSelect(Number(event.target.value))}
            >
              {spans.map((span, index) => (
                <option key={`${span.page}-${index}`} value={index}>
                  Page {span.page ?? "unknown"}, box {index + 1}
                </option>
              ))}
            </select>
          </label>
          {selectedSpan ? (
            <div className="sq-md border border-border p-3 text-sm">
              <p className="font-semibold">
                Selected source span p.{selectedSpan.page ?? "unknown"}
              </p>
              <p className="mt-2 text-muted-foreground">
                {selectedSpan.bbox
                  ? `Box ${selectedSpan.bbox.join(", ")}`
                  : "Box coordinates pending."}
              </p>
            </div>
          ) : null}
          {candidate.ancestor_headings?.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {candidate.ancestor_headings.map((heading) => (
                <span
                  className="sq-xs bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground"
                  key={heading}
                >
                  {heading}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}

function ProtectedImage({
  alt,
  className,
  url,
}: {
  alt: string
  className?: string
  url: string
}) {
  const [objectUrl, setObjectUrl] = useState<string>()

  useEffect(() => {
    let cancelled = false
    let loadedUrl: string | undefined
    const token = getAccessToken()
    fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load source page")
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
  }, [url])

  return objectUrl ? (
    <img alt={alt} className={className} src={objectUrl} />
  ) : (
    <div className="absolute inset-0 grid place-items-center text-xs text-muted-foreground">
      Source page pending
    </div>
  )
}

function RevisionDiff({ before, after }: { before: string; after: string }) {
  if (before === after) {
    return (
      <p className="text-xs text-muted-foreground">
        No textual changes from the raw extraction.
      </p>
    )
  }
  const beforeLines = before.split("\n")
  const afterLines = after.split("\n")
  const removed = beforeLines.filter((line) => !afterLines.includes(line))
  const added = afterLines.filter((line) => !beforeLines.includes(line))
  return (
    <section
      aria-label="Revision diff"
      className="sq-md grid gap-2 border border-border bg-background p-4"
    >
      <p className="text-xs font-bold uppercase text-muted-foreground">
        Revision diff (line-based)
      </p>
      {removed.map((line, index) => (
        <pre
          className="whitespace-pre-wrap bg-red-500/10 px-2 py-1 font-sans text-sm text-red-700 dark:text-red-300"
          key={`removed-${index}`}
        >
          − {line || "(blank line)"}
        </pre>
      ))}
      {added.map((line, index) => (
        <pre
          className="whitespace-pre-wrap bg-emerald-500/10 px-2 py-1 font-sans text-sm text-emerald-700 dark:text-emerald-300"
          key={`added-${index}`}
        >
          + {line || "(blank line)"}
        </pre>
      ))}
    </section>
  )
}
