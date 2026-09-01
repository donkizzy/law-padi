import { useState } from "react"
import type { IconType } from "react-icons"
import { FiRotateCcw, FiSearch, FiUploadCloud, FiXCircle } from "react-icons/fi"
import {
  LiaClipboardCheckSolid,
  LiaDatabaseSolid,
  LiaFileContractSolid,
  LiaFlaskSolid,
  LiaShieldAltSolid,
} from "react-icons/lia"

import {
  SectionHeading,
  SegmentedControl,
  SquircleButton,
  StatusBadge,
  VersionDiff,
} from "@/components/LawPadi/primitives"
import {
  corpusReleases,
  evaluationRuns,
  ingestionJobs,
  type ReviewItem,
  reviewQueue,
  sourceDocuments,
} from "@/lib/law-padi-data"
import { cn } from "@/lib/utils"

type AdminTab = "review" | "sources" | "ingestion" | "releases" | "evals"

const adminTabs: { label: string; value: AdminTab }[] = [
  { label: "Amendment review", value: "review" },
  { label: "Source documents", value: "sources" },
  { label: "Ingestion jobs", value: "ingestion" },
  { label: "Corpus releases", value: "releases" },
  { label: "Evaluation runs", value: "evals" },
]

export function AdminWorkspace() {
  const [tab, setTab] = useState<AdminTab>("review")
  const [selectedReviewId, setSelectedReviewId] = useState(reviewQueue[0]?.id)

  const selectedReview =
    reviewQueue.find((item) => item.id === selectedReviewId) ?? reviewQueue[0]

  return (
    <section className="px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
      <div className="mx-auto w-full max-w-7xl">
        <SectionHeading
          action={
            <SquircleButton type="button">
              <FiUploadCloud className="size-4" aria-hidden />
              Upload source
            </SquircleButton>
          }
          kicker="Internal legal operations"
          title="Review the evidence layer."
        >
          A restrained workspace for source documents, ingestion jobs, amendment
          review, corpus releases and evaluation runs.
        </SectionHeading>

        <div className="mb-6 grid gap-3 md:grid-cols-4">
          <MetricCard
            icon={LiaFileContractSolid}
            label="Verified sources"
            value="42"
          />
          <MetricCard
            icon={LiaClipboardCheckSolid}
            label="Review queue"
            value="18"
          />
          <MetricCard
            icon={LiaDatabaseSolid}
            label="Corpus version"
            value="0.3.0"
          />
          <MetricCard icon={LiaFlaskSolid} label="Eval pass rate" value="94%" />
        </div>

        <div className="mb-6 overflow-x-auto">
          <SegmentedControl
            ariaLabel="Legal operations tabs"
            onChange={setTab}
            options={adminTabs}
            value={tab}
          />
        </div>

        {tab === "review" && selectedReview ? (
          <ReviewScreen
            onSelect={setSelectedReviewId}
            selected={selectedReview}
            selectedId={selectedReviewId}
          />
        ) : null}
        {tab === "sources" ? <SourceDocuments /> : null}
        {tab === "ingestion" ? <IngestionJobs /> : null}
        {tab === "releases" ? <CorpusReleases /> : null}
        {tab === "evals" ? <EvaluationRuns /> : null}
      </div>
    </section>
  )
}

function MetricCard({
  icon: Icon,
  label,
  value,
}: {
  icon: IconType
  label: string
  value: string
}) {
  return (
    <div className="sq-lg border border-border bg-card p-4 shadow-[var(--shadow-subtle)]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <span className="text-xs font-semibold text-muted-foreground">
          {label}
        </span>
        <span className="sq-sm grid size-9 place-items-center bg-accent text-accent-foreground">
          <Icon className="size-4" aria-hidden />
        </span>
      </div>
      <p className="font-legal text-3xl leading-none text-foreground">
        {value}
      </p>
    </div>
  )
}

function ReviewScreen({
  selected,
  selectedId,
  onSelect,
}: {
  selected: ReviewItem
  selectedId?: string
  onSelect: (id: string) => void
}) {
  const [decision, setDecision] = useState<
    "approved" | "rejected" | "correction" | null
  >(null)

  return (
    <div className="grid gap-5 xl:grid-cols-[19rem_minmax(0,1fr)_20rem]">
      <aside className="sq-lg border border-border bg-card p-4 shadow-[var(--shadow-subtle)]">
        <h2 className="mb-4 text-sm font-bold text-foreground">Review queue</h2>
        <div className="grid gap-2">
          {reviewQueue.map((item) => (
            <button
              className={cn(
                "sq-md border p-3 text-left transition focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25",
                item.id === selectedId
                  ? "border-primary/30 bg-accent text-accent-foreground"
                  : "border-border bg-card text-foreground hover:bg-secondary",
              )}
              key={item.id}
              onClick={() => {
                onSelect(item.id)
                setDecision(null)
              }}
              type="button"
            >
              <span className="text-xs font-bold text-[color:var(--legal-blue)]">
                {item.id}
              </span>
              <span className="mt-1 block text-sm font-semibold">
                {item.targetProvision}
              </span>
              <span className="mt-1 block text-xs text-muted-foreground">
                {item.source} - {item.confidence}
              </span>
            </button>
          ))}
        </div>
      </aside>

      <main className="grid gap-5">
        <section className="sq-lg border border-border bg-card p-5 shadow-[var(--shadow-subtle)]">
          <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="mb-2 text-[0.72rem] font-bold uppercase text-muted-foreground">
                Detected target provision
              </div>
              <h2 className="font-legal text-2xl leading-tight text-foreground">
                {selected.targetProvision}
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Source: {selected.source}, {selected.page}
              </p>
            </div>
            <StatusBadge
              label={
                selected.status === "needs-correction"
                  ? "Needs correction"
                  : "Needs review"
              }
              status={
                selected.status === "needs-correction" ? "warning" : "proposed"
              }
            />
          </div>

          <VersionDiff
            current={selected.newWording}
            previous={selected.oldWording}
          />
        </section>

        <section className="sq-lg border border-border bg-card p-5 shadow-[var(--shadow-subtle)]">
          <div className="mb-4 flex items-center gap-2 text-[0.72rem] font-bold uppercase text-muted-foreground">
            <FiSearch className="size-4" aria-hidden />
            Source document
          </div>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_14rem]">
            <div className="sq-md border border-border bg-secondary/50 p-4">
              <p className="font-legal text-lg leading-tight text-foreground">
                {selected.source}
              </p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Page evidence is reviewed beside the detected wording before any
                provision version can move into a corpus release.
              </p>
            </div>
            <div className="grid gap-2 text-sm">
              <Meta label="Source page" value={selected.page} />
              <Meta label="Parser confidence" value={selected.confidence} />
              <Meta label="Reviewer" value={selected.reviewer} />
            </div>
          </div>
        </section>
      </main>

      <aside className="sq-lg border border-border bg-card p-5 shadow-[var(--shadow-subtle)]">
        <h2 className="font-legal text-xl leading-tight text-foreground">
          Review action
        </h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Approved changes can enter a candidate corpus release. Corrections go
          back to human review with the source page attached.
        </p>
        <div className="mt-5 grid gap-2">
          <SquircleButton onClick={() => setDecision("approved")} type="button">
            <LiaShieldAltSolid className="size-4" aria-hidden />
            Approve
          </SquircleButton>
          <SquircleButton
            onClick={() => setDecision("correction")}
            type="button"
            variant="outline"
          >
            <FiRotateCcw className="size-4" aria-hidden />
            Needs correction
          </SquircleButton>
          <SquircleButton
            onClick={() => setDecision("rejected")}
            type="button"
            variant="danger"
          >
            <FiXCircle className="size-4" aria-hidden />
            Reject
          </SquircleButton>
        </div>
        {decision ? (
          <div className="sq-md mt-5 border border-border bg-secondary p-4 text-sm leading-6 text-muted-foreground">
            Decision staged:{" "}
            <span className="font-semibold text-foreground">{decision}</span>.
            Connect this action to the review API when the legal backend is
            ready.
          </div>
        ) : null}
      </aside>
    </div>
  )
}

function SourceDocuments() {
  return (
    <DataPanel
      columns={["Document", "Authority", "Status", "Retrieved"]}
      rows={sourceDocuments.map((source) => [
        source.title,
        source.authority,
        source.status,
        source.retrieved,
      ])}
    />
  )
}

function IngestionJobs() {
  return (
    <div className="sq-lg overflow-hidden border border-border bg-card shadow-[var(--shadow-subtle)]">
      {ingestionJobs.map((job) => (
        <div
          className="grid gap-3 border-b border-border p-4 last:border-b-0 lg:grid-cols-[7rem_minmax(0,1fr)_10rem_6rem]"
          key={job.id}
        >
          <span className="text-xs font-bold text-[color:var(--legal-blue)]">
            {job.id}
          </span>
          <span>
            <span className="block text-sm font-semibold text-foreground">
              {job.source}
            </span>
            <span className="mt-1 block text-xs text-muted-foreground">
              {job.updated}
            </span>
          </span>
          <span className="text-sm text-muted-foreground">{job.status}</span>
          <span>
            <span className="sq-xs block h-2 overflow-hidden bg-secondary">
              <span
                className="block h-full bg-primary"
                style={{ width: job.progress }}
              />
            </span>
            <span className="mt-1 block text-xs font-semibold text-muted-foreground">
              {job.progress}
            </span>
          </span>
        </div>
      ))}
    </div>
  )
}

function CorpusReleases() {
  return (
    <DataPanel
      columns={["Version", "Status", "Evidence", "Notes"]}
      rows={corpusReleases.map((release) => [
        release.version,
        release.status,
        release.evidence,
        release.notes,
      ])}
    />
  )
}

function EvaluationRuns() {
  return (
    <DataPanel
      columns={["Run", "Status", "Score", "Focus"]}
      rows={evaluationRuns.map((run) => [
        run.name,
        run.status,
        run.score,
        run.focus,
      ])}
    />
  )
}

function DataPanel({ columns, rows }: { columns: string[]; rows: string[][] }) {
  return (
    <div className="sq-lg overflow-x-auto border border-border bg-card shadow-[var(--shadow-subtle)]">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="bg-secondary text-xs font-bold uppercase text-muted-foreground">
          <tr>
            {columns.map((column) => (
              <th className="px-4 py-3" key={column}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr className="border-t border-border" key={row.join("-")}>
              {row.map((cell, index) => (
                <td
                  className={cn(
                    "px-4 py-4 text-muted-foreground",
                    index === 0 && "font-semibold text-foreground",
                  )}
                  key={`${row[0]}-${cell}`}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-border py-2 last:border-b-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-semibold text-foreground">{value}</span>
    </div>
  )
}
