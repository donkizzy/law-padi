import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { FormEvent, ReactElement, ReactNode } from "react"
import { cloneElement, isValidElement, useEffect, useState } from "react"
import type { IconType } from "react-icons"
import {
  FiAlertTriangle,
  FiCheckCircle,
  FiClock,
  FiDatabase,
  FiFileText,
  FiPauseCircle,
  FiRefreshCcw,
  FiRotateCcw,
  FiSearch,
  FiShield,
  FiUploadCloud,
  FiXCircle,
} from "react-icons/fi"
import {
  LiaClipboardCheckSolid,
  LiaFileContractSolid,
  LiaFlaskSolid,
} from "react-icons/lia"

import {
  type AdminOperationalAlertPublic,
  AdminService,
  type CompletedMultipartPart,
  type CompositeReleaseCreate,
  type CorpusReleaseManifestPublic,
  type CorpusReleasePublic,
  type CorpusReleasePublicationEvidencePublic,
  type CorpusReleasePublishRequest,
  type CorpusReleaseValidationRequest,
  type EmbeddingBenchmarkPublic,
  type ExtractionCandidateStatus,
  type IngestionEventPublic,
  type IngestionRunControlRequest,
  type IngestionRunDetail,
  type IngestionRunPublic,
  type PageInclusionStatus,
  type PageSelectionUpdate,
  type ReviewDecisionCreate,
  type ReviewDecisionType,
  type ReviewItemPublic,
  type ReviewItemUpdate,
  type SourceDocumentPublic,
  type SourcePagePublic,
  type SourceUploadCreate,
  type SourceUploadPublic,
} from "@/client"
import { client } from "@/client/client.gen"
import { CandidateStructureEditor } from "@/components/LawPadi/CandidateStructureEditor"
import { ComposeReleaseForm } from "@/components/LawPadi/ComposeReleaseForm"
import { DeriveProvisionForm } from "@/components/LawPadi/DeriveProvisionForm"
import {
  SectionHeading,
  SegmentedControl,
  SquircleButton,
} from "@/components/LawPadi/primitives"
import { ResolveReviewIssueForm } from "@/components/LawPadi/ResolveReviewIssueForm"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import useCustomToast from "@/hooks/useCustomToast"
import { getAccessToken } from "@/lib/session"
import { cn } from "@/lib/utils"

type AdminTab = "runs" | "pages" | "review" | "releases" | "benchmarks"

type UploadFormState = {
  instrument_slug: string
  instrument_title: string
  instrument_short_title: string
  instrument_year: string
  instrument_status: SourceUploadCreate["instrument_status"]
  enacted_at: string
  effective_at: string
  ceased_at: string
  is_legal_revision: boolean
  legal_revision_effective_at: string
  source_title: string
  authority: string
  source_url: string
  source_tier: SourceUploadCreate["source_tier"]
  published_at: string
  retrieved_at: string
}

type UploadMutationInput = {
  file: File
  metadata: SourceUploadCreate
}

type PutSourceObjectResult = {
  completedParts?: CompletedMultipartPart[]
  expectedVersion: number
}

type RunEventsStreamState = {
  events: IngestionEventPublic[]
  lastEventId?: string
  status: "idle" | "connecting" | "streaming" | "reconnecting" | "polling"
}

type SourceSpanPreview = {
  bbox?: number[]
  page?: number
  width: number
  height: number
}

type ReleaseManifestSourcePreview = {
  authority?: string
  id?: string
  pageCountLabel?: string
  title?: string
}

type ReleaseManifestEntryPreview = {
  canonicalPath?: string
  id?: string
  pageRange?: string
}

type PageBoundaryDraft = Pick<
  SourcePagePublic,
  "inclusion_reason" | "inclusion_status"
>

const adminTabs: { label: string; value: AdminTab }[] = [
  { label: "Ingestion runs", value: "runs" },
  { label: "Page boundaries", value: "pages" },
  { label: "Review queue", value: "review" },
  { label: "Corpus releases", value: "releases" },
  { label: "Benchmarks", value: "benchmarks" },
]

const inputClass =
  "sq-sm min-h-10 border border-input bg-background px-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-ring/20"
const multipartChunkBytes = 100 * 1024 * 1024
const pageInclusionOptions: {
  label: string
  value: PageInclusionStatus
}[] = [
  { label: "Include", value: "included" },
  { label: "Exclude", value: "excluded" },
  { label: "Suggested include", value: "suggested_include" },
  { label: "Suggested exclude", value: "suggested_exclude" },
]

export function AdminWorkspace() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [tab, setTab] = useState<AdminTab>("runs")
  const [uploadOpen, setUploadOpen] = useState(false)
  const [selectedRunId, setSelectedRunId] = useState<string>()
  const [selectedReviewId, setSelectedReviewId] = useState<string>()
  const [reviewOffset, setReviewOffset] = useState(0)
  const [reviewFilter, setReviewFilter] = useState({ path: "", page: "" })
  const [reviewStatus, setReviewStatus] =
    useState<ExtractionCandidateStatus>("needs_review")
  const [selectedReleaseId, setSelectedReleaseId] = useState<string>()

  const metricsQuery = useQuery({
    queryKey: ["admin", "metrics"],
    queryFn: async () => (await AdminService.readAdminMetrics()).data,
    refetchInterval: 5000,
  })

  const alertsQuery = useQuery({
    queryKey: ["admin", "alerts"],
    queryFn: async () => (await AdminService.readAdminAlerts()).data,
    refetchInterval: 5000,
  })

  const runsQuery = useQuery({
    queryKey: ["admin", "ingestion-runs"],
    queryFn: async () => (await AdminService.readIngestionRuns()).data,
    refetchInterval: 5000,
  })

  const selectedRunQuery = useQuery({
    queryKey: ["admin", "ingestion-runs", selectedRunId],
    queryFn: async () =>
      (
        await AdminService.readIngestionRun({
          path: { run_id: selectedRunId ?? "" },
        })
      ).data,
    enabled: Boolean(selectedRunId),
    refetchInterval: 5000,
  })

  const pagesQuery = useQuery({
    queryKey: ["admin", "ingestion-runs", selectedRunId, "pages"],
    queryFn: async () =>
      (
        await AdminService.readIngestionRunPages({
          path: { run_id: selectedRunId ?? "" },
        })
      ).data,
    enabled: Boolean(selectedRunId),
    refetchInterval: 5000,
  })

  const reviewsQuery = useQuery({
    queryKey: [
      "admin",
      "review-items",
      selectedRunId,
      reviewStatus,
      reviewOffset,
      reviewFilter,
    ],
    queryFn: async () =>
      (
        await AdminService.readReviewItems({
          query: {
            run_id: selectedRunId,
            status: reviewStatus,
            skip: reviewOffset,
            limit: 100,
            path: reviewFilter.path || undefined,
            page: reviewFilter.page ? Number(reviewFilter.page) : undefined,
          },
        })
      ).data,
    refetchInterval: 5000,
  })

  useEffect(() => {
    const count = reviewsQuery.data?.count
    if (count !== undefined && reviewOffset > 0 && reviewOffset >= count) {
      setReviewOffset(Math.max(0, Math.floor((count - 1) / 100) * 100))
    }
  }, [reviewsQuery.data?.count, reviewOffset])

  const releasesQuery = useQuery({
    queryKey: ["admin", "corpus-releases"],
    queryFn: async () => (await AdminService.readCorpusReleases()).data,
    refetchInterval: 5000,
  })

  const benchmarkQuery = useQuery({
    queryKey: ["admin", "embedding-benchmarks", selectedReleaseId],
    queryFn: async () =>
      (
        await AdminService.readEmbeddingBenchmark({
          path: { release_id: selectedReleaseId ?? "" },
        })
      ).data,
    enabled: Boolean(selectedReleaseId),
    refetchInterval: 5000,
  })

  const releaseManifestQuery = useQuery({
    queryKey: ["admin", "corpus-releases", selectedReleaseId, "manifest"],
    queryFn: async () =>
      (
        await AdminService.readReleaseManifest({
          path: { release_id: selectedReleaseId ?? "" },
        })
      ).data,
    enabled: Boolean(selectedReleaseId),
    refetchInterval: 5000,
    retry: false,
  })

  const publicationEvidenceQuery = useQuery({
    queryKey: [
      "admin",
      "corpus-releases",
      selectedReleaseId,
      "publication-evidence",
    ],
    queryFn: async () =>
      (
        await AdminService.readReleasePublicationEvidence({
          path: { release_id: selectedReleaseId ?? "" },
        })
      ).data,
    enabled: Boolean(selectedReleaseId),
    refetchInterval: 5000,
  })

  const myRolesQuery = useQuery({
    queryKey: ["admin", "my-roles"],
    queryFn: async () => (await AdminService.readMyAdminRoles()).data,
    refetchInterval: 30000,
  })

  const auditEventsQuery = useQuery({
    queryKey: ["admin", "audit-events", selectedReleaseId],
    queryFn: async () =>
      (
        await AdminService.readAuditEvents({
          query: { entity_id: selectedReleaseId, limit: 50 },
        })
      ).data,
    enabled: Boolean(selectedReleaseId),
    refetchInterval: 10000,
  })

  const myRoles = myRolesQuery.data?.roles ?? []
  const isSuperuser = Boolean(myRolesQuery.data?.is_superuser)
  const canUpload = isSuperuser || myRoles.includes("ingestion_uploader")
  const canReview = isSuperuser || myRoles.includes("legal_reviewer")
  const canPublish = isSuperuser || myRoles.includes("corpus_publisher")

  const invalidateAdmin = () =>
    queryClient.invalidateQueries({ queryKey: ["admin"] })

  const uploadMutation = useMutation({
    mutationFn: uploadSourcePdf,
    onSuccess: (result) => {
      setUploadOpen(false)
      if (result.run?.id) {
        setSelectedRunId(result.run.id)
        setTab("runs")
      }
      showSuccessToast(
        result.duplicate
          ? "Duplicate source linked to the existing document."
          : "Source upload completed and ingestion queued.",
      )
      invalidateAdmin()
    },
    onError: (error) =>
      showErrorToast(error instanceof Error ? error.message : "Upload failed."),
  })

  const runControlMutation = useMutation({
    mutationFn: ({
      action,
      run,
      reason,
    }: {
      action: "retry" | "cancel" | "resume"
      run: IngestionRunPublic | IngestionRunDetail
      reason?: string
    }) => controlRun(action, run, reason),
    onSuccess: (run) => {
      setSelectedRunId(run.id)
      showSuccessToast("Run control saved.")
      invalidateAdmin()
    },
    onError: (error) =>
      showErrorToast(
        error instanceof Error ? error.message : "Run control failed.",
      ),
  })

  const pageSelectionMutation = useMutation({
    mutationFn: ({
      runId,
      body,
    }: {
      runId: string
      body: PageSelectionUpdate
    }) =>
      AdminService.patchPageSelection({
        path: { run_id: runId },
        body,
      }),
    onSuccess: () => {
      showSuccessToast("Page boundaries saved.")
      invalidateAdmin()
    },
    onError: (error) =>
      showErrorToast(
        error instanceof Error ? error.message : "Page confirmation failed.",
      ),
  })

  const reviewUpdateMutation = useMutation({
    mutationFn: ({
      candidateId,
      body,
    }: {
      candidateId: string
      body: ReviewItemUpdate
    }) =>
      AdminService.patchReviewItem({
        path: { candidate_id: candidateId },
        body,
      }),
    onSuccess: () => {
      showSuccessToast("Review revision saved.")
      invalidateAdmin()
    },
    onError: (error) =>
      showErrorToast(
        error instanceof Error ? error.message : "Review save failed.",
      ),
  })

  const reviewDecisionMutation = useMutation({
    mutationFn: ({
      candidateId,
      body,
    }: {
      candidateId: string
      body: ReviewDecisionCreate
    }) =>
      AdminService.decideReviewItem({
        path: { candidate_id: candidateId },
        body,
      }),
    onSuccess: () => {
      showSuccessToast("Review decision recorded.")
      invalidateAdmin()
    },
    onError: (error) =>
      showErrorToast(
        error instanceof Error ? error.message : "Review decision failed.",
      ),
  })

  const sourceVerificationMutation = useMutation({
    mutationFn: ({
      source,
      reason,
    }: {
      source: SourceDocumentPublic
      reason: string
    }) => verifySourceDocument(source, reason),
    onSuccess: () => {
      showSuccessToast("Source document verified.")
      invalidateAdmin()
    },
    onError: (error) =>
      showErrorToast(
        error instanceof Error ? error.message : "Source verification failed.",
      ),
  })

  const releaseMutation = useMutation({
    mutationFn: ({
      release,
      action,
      superuserOverrideReason,
    }: {
      release: CorpusReleasePublic
      action: "validate" | "publish"
      superuserOverrideReason?: string
    }) => mutateRelease(release, action, superuserOverrideReason),
    onSuccess: (releaseId) => {
      setSelectedReleaseId(releaseId)
      showSuccessToast("Corpus release updated.")
      invalidateAdmin()
    },
    onError: (error) =>
      showErrorToast(
        error instanceof Error ? error.message : "Release action failed.",
      ),
  })

  const composeMutation = useMutation({
    mutationFn: async (body: CompositeReleaseCreate) =>
      (await AdminService.composeRelease({ body })).data,
    onSuccess: (release) => {
      setSelectedReleaseId(release.id)
      const composition = release.validation_report?.composition
      if (
        composition &&
        typeof composition === "object" &&
        "run_id" in composition &&
        typeof composition.run_id === "string"
      )
        setSelectedRunId(composition.run_id)
      showSuccessToast("Release composed. Retrieval build queued.")
      invalidateAdmin()
    },
    onError: (error) =>
      showErrorToast(
        error instanceof Error ? error.message : "Release composition failed.",
      ),
  })

  const runs = runsQuery.data?.data ?? []
  const reviews = reviewsQuery.data?.data ?? []
  const releases = releasesQuery.data?.data ?? []
  const alerts = alertsQuery.data?.data ?? []
  const selectedRun =
    selectedRunQuery.data ?? runs.find((run) => run.id === selectedRunId)
  const selectedReview =
    reviews.find((review) => review.id === selectedReviewId) ?? reviews[0]
  const selectedRelease =
    releases.find((release) => release.id === selectedReleaseId) ?? releases[0]
  const runEventsStream = useRunEventsStream(selectedRunId)
  const selectedRunDetail = selectedRunQuery.data
    ? {
        ...selectedRunQuery.data,
        events: mergeRunEvents(
          selectedRunQuery.data.events,
          runEventsStream.events,
        ),
      }
    : undefined

  useEffect(() => {
    if (!selectedRunId && runs[0]) {
      setSelectedRunId(runs[0].id)
    }
  }, [runs, selectedRunId])

  useEffect(() => {
    if (!selectedReviewId && reviews[0]) {
      setSelectedReviewId(reviews[0].id)
    }
    if (selectedReviewId && reviews.length && !selectedReview) {
      setSelectedReviewId(reviews[0].id)
    }
  }, [reviews, selectedReview, selectedReviewId])

  useEffect(() => {
    if (!selectedReleaseId && releases[0]) {
      setSelectedReleaseId(releases[0].id)
    }
  }, [releases, selectedReleaseId])

  const metrics = metricsQuery.data

  return (
    <section className="px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
      <div className="mx-auto w-full max-w-7xl">
        <SectionHeading
          action={
            <SquircleButton
              disabled={!canUpload}
              onClick={() => setUploadOpen(true)}
              title={
                canUpload
                  ? "Upload a Constitution PDF"
                  : "Requires the ingestion_uploader role"
              }
              type="button"
            >
              <FiUploadCloud className="size-4" aria-hidden />
              Upload source
            </SquircleButton>
          }
          kicker="Internal legal operations"
          title="Review the evidence layer."
        >
          Source ingestion, review, indexing and release controls.
        </SectionHeading>

        <div className="mb-6 grid gap-3 md:grid-cols-5">
          <MetricCard
            icon={LiaFileContractSolid}
            label="Active runs"
            value={formatMetric(metrics?.active_runs)}
          />
          <MetricCard
            icon={FiPauseCircle}
            label="Blocked runs"
            value={formatMetric(metrics?.blocked_runs)}
          />
          <MetricCard
            icon={FiXCircle}
            label="Failed runs"
            value={formatMetric(metrics?.failed_runs)}
          />
          <MetricCard
            icon={FiShield}
            label="Queue depth"
            value={formatMetric(metrics?.queue_depth)}
          />
          <MetricCard
            icon={FiClock}
            label="Worker heartbeat"
            value={formatDateTime(metrics?.worker_heartbeat)}
          />
          <MetricCard
            icon={FiFileText}
            label="Pages processed"
            value={formatMetric(metrics?.pages_processed)}
          />
          <MetricCard
            icon={FiRefreshCcw}
            label="OCR fallback"
            value={formatPercent(metrics?.ocr_fallback_rate)}
          />
          <MetricCard
            icon={LiaClipboardCheckSolid}
            label="Review issues"
            value={formatMetric(metrics?.review_issues)}
          />
          <MetricCard
            icon={FiCheckCircle}
            label="Auto-approved"
            value={formatPercent(metrics?.auto_approval_rate)}
          />
          <MetricCard
            icon={LiaFlaskSolid}
            label="Embedding"
            value={formatPercent(metrics?.embedding_progress)}
          />
          <MetricCard
            icon={FiDatabase}
            label="Production"
            value={metrics?.current_production_release ?? "None"}
          />
        </div>

        <OperationalAlerts alerts={alerts} isLoading={alertsQuery.isLoading} />

        <div className="mb-6 overflow-x-auto">
          <SegmentedControl
            ariaLabel="Legal operations tabs"
            onChange={setTab}
            options={adminTabs}
            value={tab}
          />
        </div>

        {tab === "runs" ? (
          <RunWorkspace
            detail={selectedRunDetail}
            eventStream={runEventsStream}
            isLoading={runsQuery.isLoading}
            isMutating={runControlMutation.isPending}
            onControl={(action, run, reason) =>
              runControlMutation.mutate({ action, run, reason })
            }
            onSelect={(id) => {
              setSelectedRunId(id)
              setReviewOffset(0)
              setSelectedReviewId(undefined)
            }}
            runs={runs}
            selected={selectedRun}
            selectedId={selectedRunId}
          />
        ) : null}

        {tab === "pages" ? (
          <PageBoundaryWorkspace
            isLoading={pagesQuery.isLoading}
            isMutating={pageSelectionMutation.isPending}
            onConfirm={(pages) => {
              if (!selectedRunId) return
              pageSelectionMutation.mutate({
                runId: selectedRunId,
                body: pageSelectionBody(pages, selectedRun),
              })
            }}
            pages={pagesQuery.data?.data ?? []}
            selectedRun={selectedRun}
          />
        ) : null}

        {tab === "review" ? (
          <ReviewWorkspace
            canReview={canReview}
            canOverride={isSuperuser}
            totalCount={reviewsQuery.data?.count ?? 0}
            pageOffset={reviewOffset}
            onPageChange={setReviewOffset}
            filter={reviewFilter}
            onFilter={(value) => {
              setReviewFilter(value)
              setReviewOffset(0)
              setSelectedReviewId(undefined)
            }}
            statusFilter={reviewStatus}
            onStatusFilterChange={(value) => {
              setReviewStatus(value)
              setReviewOffset(0)
              setSelectedReviewId(undefined)
            }}
            isLoading={reviewsQuery.isLoading}
            isMutating={
              reviewUpdateMutation.isPending ||
              reviewDecisionMutation.isPending ||
              sourceVerificationMutation.isPending
            }
            onDecide={(candidateId, body) =>
              reviewDecisionMutation.mutate({ candidateId, body })
            }
            onSave={(candidateId, body) =>
              reviewUpdateMutation.mutate({ candidateId, body })
            }
            onSelect={setSelectedReviewId}
            onDerivedCreated={(id) => {
              setReviewStatus("needs_review")
              setReviewOffset(0)
              setReviewFilter({ path: "", page: "" })
              setSelectedReviewId(id)
            }}
            onVerifySource={(source, reason) =>
              sourceVerificationMutation.mutate({ source, reason })
            }
            reviews={reviews}
            pages={pagesQuery.data?.data ?? []}
            selected={selectedReview}
            selectedId={selectedReviewId}
          />
        ) : null}

        {tab === "releases" ? (
          <ReleaseWorkspace
            auditEvents={auditEventsQuery.data?.data ?? []}
            benchmark={benchmarkQuery.data}
            canPublish={canPublish}
            canOverride={isSuperuser}
            evidence={publicationEvidenceQuery.data}
            isBenchmarkLoading={benchmarkQuery.isLoading}
            isEvidenceLoading={publicationEvidenceQuery.isLoading}
            isLoading={releasesQuery.isLoading}
            isManifestLoading={releaseManifestQuery.isLoading}
            isMutating={releaseMutation.isPending}
            isComposing={composeMutation.isPending}
            onCompose={(body) => composeMutation.mutate(body)}
            manifest={releaseManifestQuery.data}
            onMutate={(release, action, superuserOverrideReason) =>
              releaseMutation.mutate({
                release,
                action,
                superuserOverrideReason,
              })
            }
            onSelect={setSelectedReleaseId}
            releases={releases}
            selected={selectedRelease}
            selectedId={selectedReleaseId}
          />
        ) : null}

        {tab === "benchmarks" ? (
          <BenchmarkWorkspace
            benchmark={benchmarkQuery.data}
            isLoading={benchmarkQuery.isLoading}
            onSelect={setSelectedReleaseId}
            releases={releases}
            selectedId={selectedReleaseId}
          />
        ) : null}
      </div>

      <UploadSourceDialog
        isOpen={uploadOpen}
        isUploading={uploadMutation.isPending}
        onOpenChange={setUploadOpen}
        onUpload={(input) => uploadMutation.mutate(input)}
      />
    </section>
  )
}

function useRunEventsStream(runId?: string): RunEventsStreamState {
  const queryClient = useQueryClient()
  const [streamState, setStreamState] = useState<RunEventsStreamState>({
    events: [],
    status: "idle",
  })

  useEffect(() => {
    if (!runId) {
      setStreamState({ events: [], status: "idle" })
      return
    }

    const controller = new AbortController()
    let isCurrentRun = true

    setStreamState({ events: [], status: "connecting" })

    const consumeEvents = async () => {
      try {
        const stream = await AdminService.streamIngestionRunEvents({
          onSseError: () => {
            if (!isCurrentRun) return
            setStreamState((current) => ({
              ...current,
              status: current.lastEventId ? "reconnecting" : "polling",
            }))
          },
          path: { run_id: runId },
          signal: controller.signal,
          sseDefaultRetryDelay: 1000,
          sseMaxRetryDelay: 5000,
        })

        for await (const event of stream.stream) {
          if (!isCurrentRun) break
          const runEvent = parseRunEvent(event)
          if (!runEvent) continue
          setStreamState((current) => ({
            events: mergeRunEvents(current.events, [runEvent]),
            lastEventId: String(runEvent.sequence),
            status: "streaming",
          }))
          void queryClient.invalidateQueries({
            queryKey: ["admin", "ingestion-runs"],
          })
          void queryClient.invalidateQueries({
            queryKey: ["admin", "ingestion-runs", runId],
          })
          if (
            runEvent.stage === "profiling" ||
            runEvent.stage === "awaiting_page_confirmation"
          ) {
            void queryClient.invalidateQueries({
              queryKey: ["admin", "ingestion-runs", runId, "pages"],
            })
          }
        }

        if (isCurrentRun) {
          setStreamState((current) => ({
            ...current,
            status: "polling",
          }))
        }
      } catch {
        if (!controller.signal.aborted && isCurrentRun) {
          setStreamState((current) => ({
            ...current,
            status: "polling",
          }))
        }
      }
    }

    void consumeEvents()

    return () => {
      isCurrentRun = false
      controller.abort()
    }
  }, [queryClient, runId])

  return streamState
}

function RunWorkspace({
  runs,
  selected,
  selectedId,
  detail,
  eventStream,
  isLoading,
  isMutating,
  onSelect,
  onControl,
}: {
  runs: IngestionRunPublic[]
  selected?: IngestionRunPublic | IngestionRunDetail
  selectedId?: string
  detail?: IngestionRunDetail
  eventStream: RunEventsStreamState
  isLoading: boolean
  isMutating: boolean
  onSelect: (id: string) => void
  onControl: (
    action: "retry" | "cancel" | "resume",
    run: IngestionRunPublic | IngestionRunDetail,
    reason?: string,
  ) => void
}) {
  const canResume = selected ? canResumeRun(selected) : false
  const canRetry = selected ? canRetryRun(selected) : false
  const canCancel = selected ? canCancelRun(selected) : false

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
      <Panel title="Runs" count={runs.length}>
        <ListState isLoading={isLoading} isEmpty={!runs.length} />
        <div className="grid gap-2">
          {runs.map((run) => (
            <button
              className={cn(
                "sq-md border p-3 text-left transition",
                run.id === selectedId
                  ? "border-primary bg-accent"
                  : "border-border bg-card hover:border-primary/30",
              )}
              aria-label={`${labelize(run.current_stage)} ${labelize(
                run.status,
              )}`}
              key={run.id}
              onClick={() => onSelect(run.id)}
              type="button"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold">
                    {labelize(run.current_stage)}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {shortId(run.id)}
                  </p>
                </div>
                <StatusPill status={run.status} />
              </div>
            </button>
          ))}
        </div>
      </Panel>

      <Panel title="Run detail">
        {selected ? (
          <div className="grid gap-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-lg font-bold">
                  {labelize(selected.current_stage)}
                </p>
                <p className="text-sm text-muted-foreground">
                  {selected.pipeline_version} · {shortId(selected.id)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <SquircleButton
                  disabled={isMutating || !canResume}
                  onClick={() => onControl("resume", selected)}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  <FiRotateCcw className="size-4" aria-hidden />
                  Resume
                </SquircleButton>
                <SquircleButton
                  disabled={isMutating || !canRetry}
                  onClick={() => onControl("retry", selected)}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  <FiRefreshCcw className="size-4" aria-hidden />
                  Retry
                </SquircleButton>
                <SquircleButton
                  disabled={isMutating || !canCancel}
                  onClick={() =>
                    onControl("cancel", selected, "Operator cancelled run")
                  }
                  size="sm"
                  type="button"
                  variant="danger"
                >
                  <FiPauseCircle className="size-4" aria-hidden />
                  Cancel
                </SquircleButton>
              </div>
            </div>

            <RunEventStreamStatus stream={eventStream} />

            <div className="grid gap-3 md:grid-cols-4">
              <SmallStat label="Status" value={labelize(selected.status)} />
              <SmallStat
                label="Pages"
                value={formatMetric(selected.expected_page_count)}
              />
              <SmallStat
                label="Completed"
                value={`${selected.completed_units}/${selected.total_units}`}
              />
              <SmallStat
                label="Failed"
                value={formatMetric(selected.failed_units)}
              />
            </div>

            {detail?.steps.length ? (
              <div className="grid gap-2">
                {detail.steps.map((step) => (
                  <div
                    className="grid gap-3 border-border border-b py-3 last:border-b-0 md:grid-cols-[1fr_auto]"
                    key={step.id}
                  >
                    <div>
                      <p className="text-sm font-semibold">
                        {labelize(step.stage)}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Attempts {step.attempt_count} · Units{" "}
                        {step.completed_units}/{step.total_units}
                      </p>
                    </div>
                    <StatusPill status={step.status} />
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState text="No stage records yet." />
            )}

            {detail?.events.length ? (
              <EventLog events={detail.events} />
            ) : (
              <EmptyState text="No run events yet." />
            )}
          </div>
        ) : (
          <EmptyState text="No ingestion run selected." />
        )}
      </Panel>
    </div>
  )
}

function PageBoundaryWorkspace({
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

function ReviewWorkspace({
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

// Publishing replaces the whole live corpus, so only a release that contains
// the Constitution can go live; an Act-only release is a member to compose.
function containsConstitution(release: CorpusReleasePublic) {
  return release.instrument_types?.includes("constitution") ?? false
}

function ReleaseWorkspace({
  releases,
  selected,
  selectedId,
  auditEvents = [],
  benchmark,
  canPublish = true,
  canOverride = false,
  evidence,
  isBenchmarkLoading,
  isEvidenceLoading,
  isLoading,
  isManifestLoading,
  isMutating,
  manifest,
  onSelect,
  onMutate,
  isComposing,
  onCompose,
}: {
  releases: CorpusReleasePublic[]
  selected?: CorpusReleasePublic
  selectedId?: string
  auditEvents?: {
    id: string
    action: string
    reason?: string | null
    created_at: string
  }[]
  benchmark?: EmbeddingBenchmarkPublic
  canPublish?: boolean
  canOverride?: boolean
  evidence?: CorpusReleasePublicationEvidencePublic
  isBenchmarkLoading: boolean
  isEvidenceLoading: boolean
  isLoading: boolean
  isManifestLoading: boolean
  isMutating: boolean
  isComposing: boolean
  onCompose: (body: CompositeReleaseCreate) => void
  manifest?: CorpusReleaseManifestPublic
  onSelect: (id: string) => void
  onMutate: (
    release: CorpusReleasePublic,
    action: "validate" | "publish",
    superuserOverrideReason?: string,
  ) => void
}) {
  const [overrideReason, setOverrideReason] = useState("")

  useEffect(() => {
    setOverrideReason("")
  }, [])

  const gates = selected?.validation_report?.unresolved_gates
  const sourceEdition = selected?.validation_report?.source_edition_review
  const sourceExceptions =
    sourceEdition && typeof sourceEdition === "object"
      ? (sourceEdition as Record<string, unknown>).known_exceptions
      : undefined
  const unresolvedGates = Array.isArray(gates) ? gates : []
  const releaseManifest = releaseManifestSummary(manifest)
  const benchmarkResults = benchmark?.results ?? []
  const vectorIndexes = evidence?.vector_indexes ?? []
  const retrievalIndexBuilds = evidence?.retrieval_index_builds ?? []
  const promotionAttempts = evidence?.promotion_attempts ?? []
  const actorEvidence = evidence?.actor_separation

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
      <Panel title="Corpus releases" count={releases.length}>
        <ComposeReleaseForm
          releases={releases}
          canCompose={canPublish}
          isPending={isComposing}
          onCompose={onCompose}
        />
        <ListState isLoading={isLoading} isEmpty={!releases.length} />
        <div className="grid gap-2">
          {releases.map((release) => (
            <button
              className={cn(
                "sq-md border p-3 text-left transition",
                release.id === selectedId
                  ? "border-primary bg-accent"
                  : "border-border bg-card hover:border-primary/30",
              )}
              key={release.id}
              onClick={() => onSelect(release.id)}
              type="button"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold">{release.version}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {release.evidence_count} entries
                  </p>
                  {containsConstitution(release) ? null : (
                    <p className="mt-1 text-xs font-semibold text-muted-foreground">
                      Act only · for Compose release
                    </p>
                  )}
                </div>
                <StatusPill status={release.status} />
              </div>
            </button>
          ))}
        </div>
      </Panel>

      <Panel title="Release controls">
        {selected ? (
          <div className="grid gap-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xl font-bold">{selected.version}</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Manifest {selected.source_manifest_hash ?? "pending"}
                </p>
              </div>
              <StatusPill status={selected.status} />
            </div>

            <div className="grid gap-3 md:grid-cols-4">
              <SmallStat
                label="Evidence"
                value={formatMetric(selected.evidence_count)}
              />
              <SmallStat
                label="Embedding"
                value={selected.embedding_model ?? "Pending"}
              />
              <SmallStat
                label="Parser"
                value={selected.parser_version ?? "Pending"}
              />
              <SmallStat
                label="Lock"
                value={formatMetric(selected.lock_version)}
              />
            </div>

            {selected.validation_report?.corpus_legal_status ===
            "historical" ? (
              <div className="sq-md border border-border bg-background p-4 text-sm">
                <p className="font-bold">Historical source edition</p>
                <p className="mt-1 text-muted-foreground">
                  This release preserves the uploaded edition. It has not been
                  verified as the current amended Constitution.
                </p>
                {typeof sourceExceptions === "string" ? (
                  <p className="mt-2">Source exceptions: {sourceExceptions}</p>
                ) : null}
              </div>
            ) : null}

            {unresolvedGates.length ? (
              <div className="sq-md border border-[color:var(--legal-red)]/20 bg-[color:var(--legal-red-soft)] p-4 text-sm text-[color:var(--legal-red)]">
                {unresolvedGates
                  .map((gate) => labelize(String(gate)))
                  .join(", ")}
              </div>
            ) : (
              <div className="sq-md border border-border bg-background p-4 text-sm text-muted-foreground">
                Validation gates are clear.
              </div>
            )}

            <div className="grid gap-3 md:grid-cols-2">
              <SmallStat
                label="Manifest sources"
                value={
                  isManifestLoading
                    ? "Loading"
                    : formatMetric(releaseManifest.sourceCount)
                }
              />
              <SmallStat
                label="Manifest entries"
                value={
                  isManifestLoading
                    ? "Loading"
                    : formatMetric(releaseManifest.entryCount)
                }
              />
            </div>

            <div className="sq-md border border-border bg-background p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold">Source manifest</p>
                  <p className="mt-1 max-w-3xl break-all text-xs text-muted-foreground">
                    {manifest?.source_manifest_hash ??
                      selected.source_manifest_hash ??
                      "Manifest artifact pending"}
                  </p>
                </div>
                {manifest?.artifact ? (
                  <span className="sq-xs bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
                    {labelize(manifest.artifact.artifact_type)}
                  </span>
                ) : null}
              </div>

              {releaseManifest.sources.length ? (
                <div className="mt-4 grid gap-2">
                  {releaseManifest.sources.map((source, index) => (
                    <div
                      className="sq-sm border border-border/70 bg-card p-3"
                      key={`${source.id ?? source.title}-${index}`}
                    >
                      <p className="text-sm font-semibold">
                        {source.title ?? source.id ?? "Untitled source"}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {[source.authority, source.pageCountLabel]
                          .filter(Boolean)
                          .join(" - ")}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-4 text-sm text-muted-foreground">
                  {isManifestLoading
                    ? "Loading source manifest."
                    : "Source manifest artifact has not been retained yet."}
                </p>
              )}

              {releaseManifest.entries.length ? (
                <div className="mt-4 grid gap-2">
                  {releaseManifest.entries.map((entry, index) => (
                    <div
                      className="sq-sm border border-border/70 bg-card p-3"
                      key={`${entry.canonicalPath ?? entry.id}-${index}`}
                    >
                      <p className="break-all text-sm font-semibold">
                        {entry.canonicalPath ?? entry.id ?? "Provision entry"}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {entry.pageRange ?? "Source pages pending"}
                      </p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="sq-md border border-border bg-background p-4">
              <p className="text-sm font-bold">Active retrieval targets</p>
              {evidence?.active_targets?.length ? (
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {evidence.active_targets.map((target) => (
                    <div
                      className="sq-sm border border-border/70 bg-card p-3"
                      key={target.index_kind}
                    >
                      <p className="text-sm font-semibold">
                        {target.index_kind}
                      </p>
                      <p className="mt-1 break-all text-xs text-muted-foreground">
                        Release {target.release_id} · build{" "}
                        {target.retrieval_index_build_id}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-sm text-muted-foreground">
                  No production target is active for this release.
                </p>
              )}
            </div>

            <div className="grid gap-3 xl:grid-cols-2">
              <div className="sq-md border border-border bg-background p-4">
                <p className="text-sm font-bold">
                  Embedding benchmark comparison
                </p>
                <ListState
                  isEmpty={!benchmarkResults.length}
                  isLoading={isBenchmarkLoading}
                  text="Benchmark results pending."
                />
                <div className="mt-3 grid gap-2">
                  {benchmarkResults.map((result) => (
                    <div
                      className="sq-sm border border-border/70 bg-card p-3"
                      key={result.profile_id}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold">
                            {result.model_name}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {labelize(result.provider)}
                          </p>
                        </div>
                        <StatusPill status={result.status} />
                      </div>
                      <div className="mt-3 grid gap-2 sm:grid-cols-3">
                        <SmallStat
                          label="Recall@10"
                          value={formatPercent(result.recall_at_10)}
                        />
                        <SmallStat
                          label="nDCG@10"
                          value={formatPercent(result.ndcg_at_10)}
                        />
                        <SmallStat
                          label="Cost"
                          value={formatCurrency(result.cost_usd)}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="sq-md border border-border bg-background p-4">
                <p className="text-sm font-bold">
                  {retrievalIndexBuilds.length
                    ? "pgvector validation"
                    : "Qdrant validation"}
                </p>
                {retrievalIndexBuilds.length ? (
                  <div className="mt-3 grid gap-2">
                    {retrievalIndexBuilds.map((build) => (
                      <div
                        className="sq-sm border border-border/70 bg-card p-3"
                        key={build.id}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="break-all text-sm font-semibold">
                              {build.relation_name} · {build.index_kind}
                            </p>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {build.validation_report?.is_valid === true
                                ? "Exact dense, lexical and join validation passed"
                                : "Validation evidence pending"}
                            </p>
                          </div>
                          <StatusPill status={build.status} />
                        </div>
                        <div className="mt-3 grid gap-2 sm:grid-cols-3">
                          <SmallStat
                            label="Segments"
                            value={formatMetric(build.stored_segment_count)}
                          />
                          <SmallStat
                            label="Embeddings"
                            value={formatMetric(build.stored_embedding_count)}
                          />
                          <SmallStat
                            label="Dimensions"
                            value={formatMetric(build.vector_dimensions)}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <>
                    <ListState
                      isEmpty={!vectorIndexes.length}
                      isLoading={isEvidenceLoading}
                      text="Vector index evidence pending."
                    />
                    <div className="mt-3 grid gap-2">
                      {vectorIndexes.map((index) => (
                        <div
                          className="sq-sm border border-border/70 bg-card p-3"
                          key={index.id}
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <p className="break-all text-sm font-semibold">
                                {index.collection_name}
                              </p>
                              <p className="mt-1 text-xs text-muted-foreground">
                                {vectorIndexValidationLabel(
                                  index.validation_report,
                                )}
                              </p>
                            </div>
                            <StatusPill status={index.status} />
                          </div>
                          <div className="mt-3 grid gap-2 sm:grid-cols-3">
                            <SmallStat
                              label="Points"
                              value={formatMetric(index.point_count)}
                            />
                            <SmallStat
                              label="Dimensions"
                              value={formatMetric(index.vector_dimensions)}
                            />
                            <SmallStat
                              label="Remote count"
                              value={formatMetric(
                                reportNumber(
                                  index.validation_report,
                                  "remote_point_count",
                                ),
                              )}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="grid gap-3 xl:grid-cols-2">
              <div className="sq-md border border-border bg-background p-4">
                <p className="text-sm font-bold">Actor separation</p>
                {actorEvidence ? (
                  <div className="mt-3 grid gap-3">
                    <div className="grid gap-2 sm:grid-cols-2">
                      <SmallStat
                        label="Current actor"
                        value={
                          actorEvidence.current_actor_is_source_uploader
                            ? "Source uploader"
                            : "Separate actor"
                        }
                      />
                      <SmallStat
                        label="Override"
                        value={
                          actorEvidence.superuser_override_recorded
                            ? "Recorded"
                            : "Not recorded"
                        }
                      />
                    </div>
                    <p className="break-all text-xs text-muted-foreground">
                      Uploaders:{" "}
                      {actorEvidence.source_uploader_ids.length
                        ? actorEvidence.source_uploader_ids.join(", ")
                        : "No uploader recorded"}
                    </p>
                    {actorEvidence.override_reasons?.length ? (
                      <p className="text-xs text-muted-foreground">
                        {actorEvidence.override_reasons.join("; ")}
                      </p>
                    ) : null}
                  </div>
                ) : (
                  <EmptyState text="Actor evidence pending." />
                )}
              </div>

              <div className="sq-md border border-border bg-background p-4">
                <p className="text-sm font-bold">
                  Publish and rollback history
                </p>
                <ListState
                  isEmpty={!promotionAttempts.length}
                  isLoading={isEvidenceLoading}
                  text="No promotion attempts recorded."
                />
                <div className="mt-3 grid gap-2">
                  {promotionAttempts.map((attempt) => (
                    <div
                      className="sq-sm border border-border/70 bg-card p-3"
                      key={attempt.id}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="break-all text-sm font-semibold">
                            {attempt.target_collection_name ??
                              "Collection pending"}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {attempt.rollback_completed
                              ? "Rollback completed"
                              : "Rollback not needed"}
                          </p>
                        </div>
                        <StatusPill status={attempt.status} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <FieldLabel label="Superuser override reason">
              <Input
                value={overrideReason}
                onChange={(event) => setOverrideReason(event.target.value)}
              />
            </FieldLabel>
            {actorEvidence?.current_actor_is_source_uploader ? (
              <p className="text-sm text-muted-foreground" role="note">
                You uploaded this source. Use a separate publisher account
                {canOverride
                  ? ", or enter a superuser override reason before publishing."
                  : "; only a superuser can override this requirement."}
              </p>
            ) : null}

            {!canPublish ? (
              <p
                className="sq-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm"
                role="note"
              >
                Read-only: your account lacks the corpus_publisher role.
              </p>
            ) : null}
            <div className="sq-md border border-border bg-background p-4">
              <p className="text-sm font-bold">Audit history</p>
              <ListState isEmpty={!auditEvents.length} isLoading={false} />
              <div className="mt-3 grid gap-2">
                {auditEvents.slice(0, 10).map((event) => (
                  <div
                    className="sq-sm border border-border/70 bg-card p-3 text-xs"
                    key={event.id}
                  >
                    <p className="font-semibold">{event.action}</p>
                    <p className="mt-1 text-muted-foreground">
                      {event.reason ?? "No reason recorded."} ·{" "}
                      {formatDateTime(event.created_at)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <SquircleButton
                disabled={isMutating || !canPublish}
                loading={isMutating}
                onClick={() => onMutate(selected, "validate")}
                type="button"
                variant="outline"
              >
                <FiSearch className="size-4" aria-hidden />
                Validate
              </SquircleButton>
              <SquircleButton
                disabled={
                  isMutating ||
                  !canPublish ||
                  !containsConstitution(selected) ||
                  selected.status !== "approved" ||
                  unresolvedGates.length > 0 ||
                  isEvidenceLoading ||
                  (actorEvidence?.current_actor_is_source_uploader &&
                    (!canOverride || !overrideReason.trim()))
                }
                loading={isMutating}
                onClick={() =>
                  onMutate(
                    selected,
                    "publish",
                    overrideReason.trim() || undefined,
                  )
                }
                type="button"
              >
                <FiCheckCircle className="size-4" aria-hidden />
                Publish
              </SquircleButton>
            </div>
            {containsConstitution(selected) ? null : (
              <p className="text-sm text-muted-foreground" role="note">
                This release holds an Act without the Constitution. Publishing
                it would replace the live Constitution, so add it to a release
                with Compose release and publish that instead.
              </p>
            )}
            {selected.status === "building" ||
            selected.status === "validating" ? (
              <p className="text-sm text-muted-foreground" role="note">
                Select Validate first. When all checks pass, the release becomes
                approved and Publish is enabled.
              </p>
            ) : null}
          </div>
        ) : (
          <EmptyState text="No corpus release selected." />
        )}
      </Panel>
    </div>
  )
}

function BenchmarkWorkspace({
  releases,
  selectedId,
  benchmark,
  isLoading,
  onSelect,
}: {
  releases: CorpusReleasePublic[]
  selectedId?: string
  benchmark?: EmbeddingBenchmarkPublic
  isLoading: boolean
  onSelect: (id: string) => void
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
      <Panel title="Release">
        <div className="grid gap-2">
          {releases.map((release) => (
            <button
              className={cn(
                "sq-md border p-3 text-left transition",
                release.id === selectedId
                  ? "border-primary bg-accent"
                  : "border-border bg-card hover:border-primary/30",
              )}
              key={release.id}
              onClick={() => onSelect(release.id)}
              type="button"
            >
              <p className="text-sm font-bold">{release.version}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {labelize(release.status)}
              </p>
            </button>
          ))}
        </div>
      </Panel>
      <Panel title="Embedding benchmarks">
        <p className="mb-3 text-xs text-muted-foreground">
          Winner needs Recall@10 ≥ 95%; ties break on nDCG@10, then cost and p95
          latency. Both dense candidates share the sparse_legal baseline.
        </p>
        <ListState
          isEmpty={!benchmark?.results.length}
          isLoading={isLoading}
          text="No benchmark results yet."
        />
        <div className="grid gap-2">
          {benchmark?.results.map((result) => (
            <div
              className="sq-md border border-border bg-background p-4"
              key={result.profile_id}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold">{result.model_name}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {labelize(result.provider)}
                  </p>
                </div>
                <StatusPill status={result.status} />
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-4">
                <SmallStat
                  label="Recall@10"
                  value={formatPercent(result.recall_at_10)}
                />
                <SmallStat
                  label="nDCG@10"
                  value={formatPercent(result.ndcg_at_10)}
                />
                <SmallStat
                  label="P95"
                  value={
                    result.p95_latency_ms
                      ? `${Math.round(result.p95_latency_ms)} ms`
                      : "Pending"
                  }
                />
                <SmallStat
                  label="Selected"
                  value={result.selected_for_release ? "Yes" : "No"}
                />
              </div>
            </div>
          ))}
        </div>
      </Panel>
      <OcrBenchmarkPanel />
    </div>
  )
}

function OcrBenchmarkPanel() {
  const [datasetVersion, setDatasetVersion] = useState("")
  const infoQuery = useQuery({
    queryKey: ["admin", "ocr-benchmarks", datasetVersion],
    queryFn: async () =>
      (
        await AdminService.readOcrBenchmark({
          path: { dataset_version: datasetVersion },
        })
      ).data,
    enabled: Boolean(datasetVersion.trim()),
    retry: false,
  })
  return (
    <Panel title="OCR benchmarks">
      <p className="mb-3 text-xs text-muted-foreground">
        Compare Google Document AI vs Azure Document Intelligence on the same
        versioned OCR_PAGE dataset. The winner is activated via
        MANAGED_OCR_PROVIDER configuration.
      </p>
      <div className="grid gap-2 sm:grid-cols-[2fr_auto]">
        <Input
          aria-label="OCR benchmark dataset version"
          onChange={(event) => setDatasetVersion(event.target.value)}
          placeholder="e.g. ocr-gold-v1"
          value={datasetVersion}
        />
        <SquircleButton
          disabled={!datasetVersion.trim()}
          onClick={() => infoQuery.refetch()}
          type="button"
          variant="outline"
        >
          <FiSearch className="size-4" aria-hidden />
          Load dataset
        </SquircleButton>
      </div>
      {infoQuery.data ? (
        <p className="mt-3 text-sm text-muted-foreground">
          {infoQuery.data.sample_count} pages ·{" "}
          {infoQuery.data.active_dataset_items} active items
          {infoQuery.data.winner ? ` · winner ${infoQuery.data.winner}` : ""}
        </p>
      ) : null}
      {infoQuery.data?.providers?.length ? (
        <div className="mt-3 grid gap-2">
          {infoQuery.data.providers.map((result) => (
            <div
              className="sq-md border border-border bg-background p-4"
              key={result.provider}
            >
              <p className="text-sm font-bold">{result.provider}</p>
              <div className="mt-3 grid gap-3 md:grid-cols-4">
                <SmallStat
                  label="Char accuracy"
                  value={formatPercent(result.mean_character_accuracy)}
                />
                <SmallStat
                  label="Failures"
                  value={formatMetric(result.failure_count)}
                />
                <SmallStat
                  label="Cost"
                  value={
                    result.total_cost_usd != null
                      ? `$${result.total_cost_usd}`
                      : "Pending"
                  }
                />
                <SmallStat
                  label="Mean ms"
                  value={formatMetric(result.mean_timing_ms)}
                />
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </Panel>
  )
}

function UploadSourceDialog({
  isOpen,
  isUploading,
  onOpenChange,
  onUpload,
}: {
  isOpen: boolean
  isUploading: boolean
  onOpenChange: (open: boolean) => void
  onUpload: (input: UploadMutationInput) => void
}) {
  const { showErrorToast } = useCustomToast()
  const [form, setForm] = useState<UploadFormState>(() => defaultUploadForm())
  const [file, setFile] = useState<File | null>(null)

  useEffect(() => {
    if (!isOpen) {
      setForm(defaultUploadForm())
      setFile(null)
    }
  }, [isOpen])

  const updateField = <T extends keyof UploadFormState>(
    field: T,
    value: UploadFormState[T],
  ) => setForm((current) => ({ ...current, [field]: value }))

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!file) {
      showErrorToast("Choose a PDF source file.")
      return
    }
    if (file.type && file.type !== "application/pdf") {
      showErrorToast("V1 ingestion accepts PDF sources only.")
      return
    }
    if (form.is_legal_revision && !form.legal_revision_effective_at) {
      showErrorToast("Set the legal revision effective date.")
      return
    }
    const expectedSha256 = await sha256File(file)
    onUpload({
      file,
      metadata: {
        idempotency_key: `upload-${crypto.randomUUID()}`,
        expected_size: file.size,
        expected_sha256: expectedSha256,
        original_filename: file.name,
        mime_type: "application/pdf",
        instrument_slug: form.instrument_slug.trim(),
        instrument_title: form.instrument_title.trim(),
        instrument_short_title: form.instrument_short_title.trim() || null,
        instrument_year: Number(form.instrument_year),
        instrument_status: form.instrument_status,
        enacted_at: form.enacted_at || null,
        effective_at: form.effective_at || null,
        ceased_at: form.ceased_at || null,
        is_legal_revision: form.is_legal_revision,
        legal_revision_effective_at: form.is_legal_revision
          ? form.legal_revision_effective_at
          : null,
        source_title: form.source_title.trim(),
        authority: form.authority.trim(),
        source_url: form.source_url.trim(),
        source_tier: form.source_tier,
        published_at: form.published_at,
        retrieved_at: form.retrieved_at,
      },
    })
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Upload Constitution source</DialogTitle>
        </DialogHeader>
        <form className="grid gap-5" onSubmit={handleSubmit}>
          <div className="grid gap-4 md:grid-cols-2">
            <FieldLabel label="Instrument slug">
              <Input
                required
                value={form.instrument_slug}
                onChange={(event) =>
                  updateField("instrument_slug", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Instrument year">
              <Input
                min={1}
                required
                type="number"
                value={form.instrument_year}
                onChange={(event) =>
                  updateField("instrument_year", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel className="md:col-span-2" label="Instrument title">
              <Input
                required
                value={form.instrument_title}
                onChange={(event) =>
                  updateField("instrument_title", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Short title">
              <Input
                value={form.instrument_short_title}
                onChange={(event) =>
                  updateField("instrument_short_title", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Instrument status">
              <select
                className={inputClass}
                required
                value={form.instrument_status}
                onChange={(event) =>
                  updateField(
                    "instrument_status",
                    event.target.value as UploadFormState["instrument_status"],
                  )
                }
              >
                <option value="enacted">Enacted</option>
                <option value="draft">Draft</option>
                <option value="proposed">Proposed</option>
                <option value="superseded">Superseded</option>
              </select>
            </FieldLabel>
            <FieldLabel label="Enacted date">
              <Input
                type="date"
                value={form.enacted_at}
                onChange={(event) =>
                  updateField("enacted_at", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Effective date">
              <Input
                type="date"
                value={form.effective_at}
                onChange={(event) =>
                  updateField("effective_at", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Ceased date">
              <Input
                type="date"
                value={form.ceased_at}
                onChange={(event) =>
                  updateField("ceased_at", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Legal revision">
              <div className="flex min-h-10 items-center gap-3 sq-sm border border-input bg-background px-3">
                <Checkbox
                  aria-label="Legal revision"
                  checked={form.is_legal_revision}
                  onCheckedChange={(checked) =>
                    updateField("is_legal_revision", checked === true)
                  }
                />
                <span className="text-sm font-medium">Changes current law</span>
              </div>
            </FieldLabel>
            <FieldLabel label="Revision effective date">
              <Input
                aria-required={form.is_legal_revision}
                disabled={!form.is_legal_revision}
                type="date"
                value={form.legal_revision_effective_at}
                onChange={(event) =>
                  updateField("legal_revision_effective_at", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Source title">
              <Input
                required
                value={form.source_title}
                onChange={(event) =>
                  updateField("source_title", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Authority">
              <Input
                required
                value={form.authority}
                onChange={(event) =>
                  updateField("authority", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel className="md:col-span-2" label="Source URL">
              <Input
                required
                type="url"
                value={form.source_url}
                onChange={(event) =>
                  updateField("source_url", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Source tier">
              <select
                className={inputClass}
                required
                value={form.source_tier}
                onChange={(event) =>
                  updateField(
                    "source_tier",
                    event.target.value as UploadFormState["source_tier"],
                  )
                }
              >
                <option value="official">Official</option>
                <option value="trusted_secondary">Trusted secondary</option>
                <option value="community">Community</option>
                <option value="unknown">Unknown</option>
              </select>
            </FieldLabel>
            <FieldLabel label="Published date">
              <Input
                required
                type="date"
                value={form.published_at}
                onChange={(event) =>
                  updateField("published_at", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Retrieved date">
              <Input
                required
                type="date"
                value={form.retrieved_at}
                onChange={(event) =>
                  updateField("retrieved_at", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Source file">
              <Input
                accept="application/pdf,.pdf"
                required
                type="file"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </FieldLabel>
          </div>
          <DialogFooter>
            <SquircleButton
              disabled={isUploading}
              onClick={() => onOpenChange(false)}
              type="button"
              variant="ghost"
            >
              Cancel
            </SquircleButton>
            <SquircleButton loading={isUploading} type="submit">
              <FiUploadCloud className="size-4" aria-hidden />
              Start ingestion
            </SquircleButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
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
      <p className="font-display text-3xl leading-none text-foreground">
        {value}
      </p>
    </div>
  )
}

function OperationalAlerts({
  alerts,
  isLoading,
}: {
  alerts: AdminOperationalAlertPublic[]
  isLoading: boolean
}) {
  return (
    <div className="mb-6">
      <Panel title="Operational alerts" count={alerts.length}>
        <ListState
          isEmpty={!alerts.length}
          isLoading={isLoading}
          text="No dashboard alerts."
        />
        {alerts.length ? (
          <div className="grid gap-2">
            {alerts.slice(0, 6).map((alert) => (
              <article
                className={cn(
                  "sq-md border p-4",
                  alertToneClass(alert.severity),
                )}
                key={alert.id}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 text-sm font-bold">
                      <FiAlertTriangle
                        className="size-4 shrink-0"
                        aria-hidden
                      />
                      <span>{alert.title}</span>
                    </p>
                    <p className="mt-2 break-words text-sm opacity-85">
                      {alert.message}
                    </p>
                  </div>
                  <span className="sq-xs bg-background/70 px-2 py-1 text-xs font-bold">
                    {labelize(alert.alert_type)}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-xs opacity-75">
                  <span>{labelize(alert.severity)}</span>
                  <span>{formatDateTime(alert.detected_at)}</span>
                  {alert.run_id ? (
                    <span>Run {shortId(alert.run_id)}</span>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </Panel>
    </div>
  )
}

function Panel({
  title,
  count,
  action,
  children,
}: {
  title: string
  count?: number
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="sq-lg min-w-0 border border-border bg-card p-5 shadow-[var(--shadow-subtle)]">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="font-display text-xl text-foreground">{title}</h2>
          {typeof count === "number" ? (
            <span className="sq-xs bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
              {count}
            </span>
          ) : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

function SmallStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="sq-md border border-border bg-background p-3">
      <p className="text-xs font-semibold text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-bold text-foreground">{value}</p>
    </div>
  )
}

function StatusPill({ status }: { status?: string | null }) {
  return (
    <span className="sq-xs inline-flex w-fit items-center gap-1.5 border border-border bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
      {statusIcon(status)}
      {labelize(status ?? "unknown")}
    </span>
  )
}

function statusIcon(status?: string | null) {
  if (!status) {
    return <FiClock className="size-3.5" aria-hidden />
  }
  if (
    ["succeeded", "approved", "production", "published", "ready"].includes(
      status,
    )
  ) {
    return <FiCheckCircle className="size-3.5" aria-hidden />
  }
  if (["failed", "cancelled", "rejected"].includes(status)) {
    return <FiXCircle className="size-3.5" aria-hidden />
  }
  return <FiClock className="size-3.5" aria-hidden />
}

function EventLog({
  events,
}: {
  events: NonNullable<IngestionRunDetail["events"]>
}) {
  return (
    <div className="grid gap-2">
      {events.map((event) => (
        <div
          className="grid gap-2 border-border border-b py-3 last:border-b-0 md:grid-cols-[96px_1fr]"
          key={event.id}
        >
          <span className="text-xs font-bold text-muted-foreground">
            #{event.sequence}
          </span>
          <div>
            <p className="text-sm font-semibold">
              {labelize(event.event_type)}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {event.message}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}

function TextBlock({
  title,
  children,
}: {
  title: string
  children?: ReactNode
}) {
  return (
    <div className="sq-md border border-border bg-background p-4">
      <p className="mb-3 text-xs font-bold uppercase text-muted-foreground">
        {title}
      </p>
      <pre className="whitespace-pre-wrap font-sans text-sm leading-7 text-foreground">
        {children || "No text recorded."}
      </pre>
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

function FieldLabel({
  label,
  children,
  className,
}: {
  label: string
  children: ReactNode
  className?: string
}) {
  const labelledChild = isValidElement<{ "aria-label"?: string }>(children)
    ? cloneElement(children as ReactElement<{ "aria-label"?: string }>, {
        "aria-label": children.props["aria-label"] ?? label,
      })
    : children

  return (
    <div className={cn("grid gap-2 text-sm font-semibold", className)}>
      <span>{label}</span>
      {labelledChild}
    </div>
  )
}

function ListState({
  isLoading,
  isEmpty,
  text = "No records yet.",
}: {
  isLoading: boolean
  isEmpty: boolean
  text?: string
}) {
  if (isLoading) {
    return <EmptyState text="Loading..." />
  }
  if (isEmpty) {
    return <EmptyState text={text} />
  }
  return null
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="sq-md border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
      {text}
    </div>
  )
}

function RunEventStreamStatus({ stream }: { stream: RunEventsStreamState }) {
  return (
    <div
      aria-label="Run event stream status"
      aria-live="polite"
      className="sq-md flex flex-wrap items-center gap-3 border border-border bg-background p-3 text-sm"
      role="status"
    >
      <StatusPill status={stream.status} />
      <span className="text-muted-foreground">
        {runEventStreamLabel(stream)}
      </span>
    </div>
  )
}

function runEventStreamLabel(stream: RunEventsStreamState): string {
  if (stream.status === "connecting") {
    return "Connecting to live events."
  }
  if (stream.status === "streaming") {
    return stream.lastEventId
      ? `Live events streaming from #${stream.lastEventId}.`
      : "Live events streaming."
  }
  if (stream.status === "reconnecting") {
    return "Live events reconnecting; polling every 5 seconds."
  }
  if (stream.status === "polling") {
    return "Polling every 5 seconds."
  }
  return "No live run selected."
}

function parseRunEvent(value: unknown): IngestionEventPublic | null {
  if (!value || typeof value !== "object") return null
  const candidate = value as Partial<IngestionEventPublic>
  if (
    typeof candidate.id !== "string" ||
    typeof candidate.run_id !== "string" ||
    typeof candidate.sequence !== "number" ||
    typeof candidate.event_type !== "string" ||
    typeof candidate.message !== "string"
  ) {
    return null
  }
  return candidate as IngestionEventPublic
}

function mergeRunEvents(
  existing: IngestionEventPublic[],
  incoming: IngestionEventPublic[],
): IngestionEventPublic[] {
  const events = new Map<string, IngestionEventPublic>()
  for (const event of [...existing, ...incoming]) {
    events.set(event.id || `${event.sequence}`, event)
  }
  return [...events.values()].sort(
    (left, right) => left.sequence - right.sequence,
  )
}

function canResumeRun(run: IngestionRunPublic | IngestionRunDetail): boolean {
  return run.status === "cancelled"
}

function canRetryRun(run: IngestionRunPublic | IngestionRunDetail): boolean {
  return run.status === "failed"
}

function canCancelRun(run: IngestionRunPublic | IngestionRunDetail): boolean {
  return !["published", "cancelled"].includes(run.status)
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

function sourceSpanPreviews(
  spans: ReviewItemPublic["source_spans"],
  pages: SourcePagePublic[],
): SourceSpanPreview[] {
  if (!Array.isArray(spans)) return []
  return spans.map((span) => {
    const page =
      typeof span.page_number === "number"
        ? span.page_number
        : typeof span.page === "number"
          ? span.page
          : undefined
    const sourcePage = pages.find((item) => item.page_number === page)
    const box = span.bbox
    const objectBox =
      box && typeof box === "object"
        ? (box as Record<string, unknown>)
        : undefined
    const coordinates = Array.isArray(box)
      ? box
      : objectBox
        ? [objectBox.x0, objectBox.y0, objectBox.x1, objectBox.y1]
        : undefined
    const bbox =
      coordinates?.length === 4 &&
      coordinates.every(
        (value) => typeof value === "number" && Number.isFinite(value),
      )
        ? (coordinates as number[])
        : undefined
    const space = sourcePage?.quality_signals?.coordinate_space
    const dpi =
      space &&
      typeof space === "object" &&
      "render_dpi" in space &&
      typeof space.render_dpi === "number"
        ? space.render_dpi
        : 72
    const scale = dpi / 72
    const dimensionsKnown = sourcePage?.width && sourcePage?.height
    const raster =
      space &&
      typeof space === "object" &&
      "unit" in space &&
      space.unit === "raster_pixels"
    return {
      bbox,
      page,
      width:
        dimensionsKnown || !raster ? (sourcePage?.width ?? 612) * scale : 0,
      height:
        dimensionsKnown || !raster ? (sourcePage?.height ?? 792) * scale : 0,
    }
  })
}

function releaseManifestSummary(manifest?: CorpusReleaseManifestPublic): {
  entryCount?: number
  entries: ReleaseManifestEntryPreview[]
  sourceCount?: number
  sources: ReleaseManifestSourcePreview[]
} {
  const manifestBody = manifest?.manifest
  if (!manifestBody || typeof manifestBody !== "object") {
    return { entries: [], sources: [] }
  }
  const sourceDocuments = Array.isArray(manifestBody.source_documents)
    ? manifestBody.source_documents
    : []
  const entries = Array.isArray(manifestBody.entries)
    ? manifestBody.entries
    : []
  return {
    entryCount: entries.length,
    entries: entries
      .slice(0, 4)
      .map((entry) => releaseManifestEntryPreview(entry)),
    sourceCount: sourceDocuments.length,
    sources: sourceDocuments
      .slice(0, 3)
      .map((source) => releaseManifestSourcePreview(source)),
  }
}

function releaseManifestSourcePreview(
  value: unknown,
): ReleaseManifestSourcePreview {
  if (!value || typeof value !== "object") return {}
  const source = value as Record<string, unknown>
  const pageCount =
    typeof source.page_count === "number"
      ? `${source.page_count} pages`
      : undefined
  return {
    authority:
      typeof source.authority === "string" ? source.authority : undefined,
    id: typeof source.id === "string" ? source.id : undefined,
    pageCountLabel: pageCount,
    title: typeof source.title === "string" ? source.title : undefined,
  }
}

function releaseManifestEntryPreview(
  value: unknown,
): ReleaseManifestEntryPreview {
  if (!value || typeof value !== "object") return {}
  const entry = value as Record<string, unknown>
  const pageStart =
    typeof entry.source_page_start === "number"
      ? entry.source_page_start
      : undefined
  const pageEnd =
    typeof entry.source_page_end === "number"
      ? entry.source_page_end
      : pageStart
  return {
    canonicalPath:
      typeof entry.canonical_path === "string"
        ? entry.canonical_path
        : undefined,
    id:
      typeof entry.provision_version_id === "string"
        ? entry.provision_version_id
        : undefined,
    pageRange:
      pageStart !== undefined && pageEnd !== undefined
        ? `Source pages ${pageStart}${pageEnd === pageStart ? "" : `-${pageEnd}`}`
        : undefined,
  }
}

function sourceBoxStyle(span: SourceSpanPreview) {
  const [x1, y1, x2, y2] =
    span.bbox && span.bbox.length >= 4 ? span.bbox : [0, 0, 0, 0]
  return {
    height: `${clampPercent(((y2 - y1) / span.height) * 100)}%`,
    left: `${clampPercent((x1 / span.width) * 100)}%`,
    top: `${clampPercent((y1 / span.height) * 100)}%`,
    width: `${clampPercent(((x2 - x1) / span.width) * 100)}%`,
  }
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value * 100) / 100))
}

async function uploadSourcePdf(input: UploadMutationInput) {
  const upload = (
    await AdminService.createSourceUpload({ body: input.metadata })
  ).data
  const putResult = await putSourceObject(upload, input.file)
  return (
    await AdminService.completeUpload({
      path: { upload_id: upload.id },
      body: {
        idempotency_key: `complete-${crypto.randomUUID()}`,
        expected_version: putResult.expectedVersion,
        actual_sha256: input.metadata.expected_sha256,
        completed_parts: putResult.completedParts,
      },
    })
  ).data
}

async function putSourceObject(
  upload: SourceUploadPublic,
  file: File,
): Promise<PutSourceObjectResult> {
  if (upload.multipart_required) {
    return putMultipartSourceObject(upload, file)
  }
  const token = getAccessToken()
  const response = await fetch(uploadFetchUrl(upload.upload_url), {
    method: "PUT",
    headers: {
      ...upload.upload_headers,
      ...(upload.upload_backend === "local" && token
        ? { Authorization: `Bearer ${token}` }
        : {}),
    },
    body: file,
  })
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response))
  }
  return {
    expectedVersion:
      upload.upload_backend === "local"
        ? upload.lock_version + 1
        : upload.lock_version,
  }
}

async function putMultipartSourceObject(
  upload: SourceUploadPublic,
  file: File,
): Promise<PutSourceObjectResult> {
  const partCount = Math.max(1, Math.ceil(file.size / multipartChunkBytes))
  const multipart = (
    await AdminService.createMultipartUploadParts({
      path: { upload_id: upload.id },
      body: {
        idempotency_key: `multipart-${crypto.randomUUID()}`,
        expected_version: upload.lock_version,
        part_count: partCount,
      },
    })
  ).data
  const completedParts: CompletedMultipartPart[] = []
  for (const part of multipart.parts) {
    const start = (part.part_number - 1) * multipartChunkBytes
    const end = Math.min(start + multipartChunkBytes, file.size)
    const response = await fetch(uploadFetchUrl(part.upload_url), {
      method: "PUT",
      body: file.slice(start, end),
    })
    if (!response.ok) {
      throw new Error(await responseErrorMessage(response))
    }
    const etag = response.headers.get("etag")
    if (!etag) {
      throw new Error("Multipart upload part did not return an ETag")
    }
    completedParts.push({ part_number: part.part_number, etag })
  }
  return {
    completedParts,
    expectedVersion: upload.lock_version + 1,
  }
}

function uploadFetchUrl(uploadUrl: string): string {
  const apiBaseUrl =
    client.getConfig().baseURL || import.meta.env.VITE_API_URL || ""
  if (!apiBaseUrl || /^https?:\/\//i.test(uploadUrl)) {
    return uploadUrl
  }
  return new URL(uploadUrl, apiBaseUrl).toString()
}

async function controlRun(
  action: "retry" | "cancel" | "resume",
  run: IngestionRunPublic | IngestionRunDetail,
  reason?: string,
) {
  const body: IngestionRunControlRequest = {
    idempotency_key: `${action}-${crypto.randomUUID()}`,
    expected_version: run.lock_version,
    reason,
  }
  if (action === "retry") {
    return (await AdminService.retryRun({ path: { run_id: run.id }, body }))
      .data
  }
  if (action === "cancel") {
    return (await AdminService.cancelRun({ path: { run_id: run.id }, body }))
      .data
  }
  return (await AdminService.resumeRun({ path: { run_id: run.id }, body })).data
}

async function verifySourceDocument(
  source: SourceDocumentPublic,
  reason: string,
) {
  return (
    await AdminService.verifyDocumentSource({
      path: { source_document_id: source.id },
      body: {
        idempotency_key: `verify-source-${crypto.randomUUID()}`,
        expected_version: source.lock_version,
        reason,
      },
    })
  ).data
}

async function mutateRelease(
  release: CorpusReleasePublic,
  action: "validate" | "publish",
  superuserOverrideReason?: string,
) {
  if (action === "validate") {
    const body: CorpusReleaseValidationRequest = {
      idempotency_key: `validate-${crypto.randomUUID()}`,
      expected_version: release.lock_version,
    }
    return (
      await AdminService.validateRelease({
        path: { release_id: release.id },
        body,
      })
    ).data.id
  }
  const body: CorpusReleasePublishRequest = {
    idempotency_key: `publish-${crypto.randomUUID()}`,
    expected_version: release.lock_version,
    superuser_override_reason: superuserOverrideReason ?? null,
  }
  return (
    await AdminService.publishRelease({
      path: { release_id: release.id },
      body,
    })
  ).data.release.id
}

function pageSelectionBody(
  pages: SourcePagePublic[],
  run?: IngestionRunPublic | IngestionRunDetail,
): PageSelectionUpdate {
  return {
    idempotency_key: `pages-${crypto.randomUUID()}`,
    expected_run_version: run?.lock_version ?? 1,
    pages: pages.map((page) => ({
      page_number: page.page_number,
      inclusion_status: nextInclusionStatus(page.inclusion_status),
      inclusion_reason: page.inclusion_reason ?? "Confirmed by reviewer",
      expected_version: page.lock_version,
    })),
  }
}

function nextInclusionStatus(status: PageInclusionStatus): PageInclusionStatus {
  if (status === "suggested_exclude") return "excluded"
  if (status === "suggested_include") return "included"
  return status
}

async function sha256File(file: File): Promise<string> {
  const hashBuffer = await crypto.subtle.digest(
    "SHA-256",
    await file.arrayBuffer(),
  )
  return Array.from(new Uint8Array(hashBuffer))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")
}

async function responseErrorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json()
    if (typeof payload.detail === "string") {
      return payload.detail
    }
    if (Array.isArray(payload.detail) && payload.detail[0]?.msg) {
      return payload.detail[0].msg
    }
  } catch {
    return response.statusText
  }
  return response.statusText
}

function defaultUploadForm(): UploadFormState {
  const today = new Date().toISOString().slice(0, 10)
  return {
    instrument_slug: "constitution-1999",
    instrument_title: "Constitution of the Federal Republic of Nigeria 1999",
    instrument_short_title: "CFRN 1999",
    instrument_year: "1999",
    instrument_status: "enacted",
    enacted_at: "1999-05-29",
    effective_at: "1999-05-29",
    ceased_at: "",
    is_legal_revision: false,
    legal_revision_effective_at: "",
    source_title: "CFRN 1999 official PDF",
    authority: "Official Gazette",
    source_url: "https://example.test/cfrn-1999.pdf",
    source_tier: "official",
    published_at: "1999-05-29",
    retrieved_at: today,
  }
}

function formatMetric(value?: number | null): string {
  if (typeof value !== "number") return "0"
  return new Intl.NumberFormat().format(value)
}

function formatCurrency(value?: number | null): string {
  if (typeof value !== "number") return "Pending"
  return new Intl.NumberFormat("en", {
    currency: "USD",
    maximumFractionDigits: 2,
    style: "currency",
  }).format(value)
}

function formatPercent(value?: number | null): string {
  if (typeof value !== "number") return "0%"
  return `${Math.round(value * 100)}%`
}

function formatDateTime(value?: string | null): string {
  if (!value) return "None"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Unknown"
  return new Intl.DateTimeFormat("en", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
  }).format(date)
}

function alertToneClass(severity?: string | null): string {
  if (severity === "high") {
    return "border-[color:var(--legal-red)]/30 bg-[color:var(--legal-red-soft)] text-[color:var(--legal-red)]"
  }
  if (severity === "warning") {
    return "border-[color:var(--legal-amber)]/30 bg-[color:var(--legal-amber-soft)] text-[color:var(--legal-amber)]"
  }
  return "border-border bg-background text-foreground"
}

function reportNumber(
  report: Record<string, unknown> | null | undefined,
  key: string,
): number | undefined {
  const value = report?.[key]
  return typeof value === "number" ? value : undefined
}

function vectorIndexValidationLabel(
  report: Record<string, unknown> | null | undefined,
): string {
  if (!report) return "Validation pending"
  const smokeQueries = Array.isArray(report.smoke_queries)
    ? report.smoke_queries
    : []
  const smokeQueriesPassed =
    smokeQueries.length > 0 &&
    smokeQueries.every(
      (query) =>
        Boolean(query) &&
        typeof query === "object" &&
        (query as Record<string, unknown>).passed === true,
    )
  return report.is_valid === true && smokeQueriesPassed
    ? "Validation passed"
    : "Validation has unresolved evidence"
}

function labelize(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase())
}

function shortId(value: string): string {
  return value.slice(0, 8)
}
