import {
  type QueryKey,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { useEffect, useState } from "react"
import type { IconType } from "react-icons"
import {
  FiAlertTriangle,
  FiCheckCircle,
  FiClock,
  FiDatabase,
  FiFileText,
  FiPauseCircle,
  FiRefreshCcw,
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
  type CompositeReleaseCreate,
  type CorpusReleasePublic,
  type ExtractionCandidateStatus,
  type IngestionRunDetail,
  type IngestionRunPublic,
  type PageSelectionUpdate,
  type ReviewDecisionCreate,
  type ReviewItemUpdate,
  type SourceDocumentPublic,
} from "@/client"
import {
  controlRun,
  mutateRelease,
  pageSelectionBody,
  uploadSourcePdf,
  verifySourceDocument,
} from "@/components/Constitution/admin/api"
import { BenchmarkWorkspace } from "@/components/Constitution/admin/BenchmarkWorkspace"
import {
  formatDateTime,
  formatMetric,
  formatPercent,
  labelize,
  shortId,
} from "@/components/Constitution/admin/format"
import { PageBoundaryWorkspace } from "@/components/Constitution/admin/PageBoundaryWorkspace"
import { ReleaseWorkspace } from "@/components/Constitution/admin/ReleaseWorkspace"
import { ReviewWorkspace } from "@/components/Constitution/admin/ReviewWorkspace"
import { RunWorkspace } from "@/components/Constitution/admin/RunWorkspace"
import { UploadSourceDialog } from "@/components/Constitution/admin/UploadSourceDialog"
import { ListState, Panel } from "@/components/Constitution/admin/ui"
import {
  mergeRunEvents,
  useRunEventsStream,
} from "@/components/Constitution/admin/useRunEventsStream"
import {
  SectionHeading,
  SegmentedControl,
  SquircleButton,
} from "@/components/Constitution/primitives"
import useCustomToast from "@/hooks/useCustomToast"
import {
  adminKeys,
  hasActiveWork,
  liveQuery,
  pollWhile,
} from "@/lib/admin-queries"
import { cn } from "@/lib/utils"

type AdminTab = "runs" | "pages" | "review" | "releases" | "benchmarks"

const adminTabs: { label: string; value: AdminTab }[] = [
  { label: "Ingestion runs", value: "runs" },
  { label: "Page boundaries", value: "pages" },
  { label: "Review queue", value: "review" },
  { label: "Corpus releases", value: "releases" },
  { label: "Benchmarks", value: "benchmarks" },
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

  // The stream feeds the selected run, so it is read before the queries that
  // fall back to polling when it is not delivering.
  const runEventsStream = useRunEventsStream(selectedRunId)
  const streaming = runEventsStream.status === "streaming"
  const onRunsTab = tab === "runs"
  const onPagesTab = tab === "pages"
  const onReviewTab = tab === "review"
  const onReleasesTab = tab === "releases"
  const onBenchmarksTab = tab === "benchmarks"

  // The metrics say whether the pipeline is busy, so they are always followed,
  // slowing down while nothing changes. Everything else is followed only while
  // there is work to follow and its tab is open.
  const metricsQuery = useQuery({
    queryKey: adminKeys.metrics(),
    queryFn: async () => (await AdminService.readAdminMetrics()).data,
    refetchInterval: pollWhile(true, 5_000, 30_000),
    ...liveQuery,
  })

  const alertsQuery = useQuery({
    queryKey: adminKeys.alerts(),
    queryFn: async () => (await AdminService.readAdminAlerts()).data,
    refetchInterval: pollWhile(true, 5_000, 30_000),
    ...liveQuery,
  })

  const runsQuery = useQuery({
    queryKey: adminKeys.runs(),
    queryFn: async () => (await AdminService.readIngestionRuns()).data,
    // The list is also what shows whether a run is in progress.
    refetchInterval: (query) =>
      pollWhile(
        hasActiveWork(metricsQuery.data, query.state.data?.data ?? []),
        5_000,
        30_000,
      )(query),
    ...liveQuery,
  })
  const workActive = hasActiveWork(
    metricsQuery.data,
    runsQuery.data?.data ?? [],
  )
  const followWork = (baseMs: number, maxMs = 30_000) =>
    pollWhile(workActive, baseMs, maxMs)
  // The stream refreshes the selected run as it changes; polling is its fallback.
  const followRunUnlessStreaming = pollWhile(
    workActive && !streaming,
    5_000,
    30_000,
  )

  const selectedRunQuery = useQuery({
    queryKey: adminKeys.run(selectedRunId),
    queryFn: async () =>
      (
        await AdminService.readIngestionRun({
          path: { run_id: selectedRunId ?? "" },
        })
      ).data,
    enabled: Boolean(selectedRunId) && (onRunsTab || onPagesTab),
    refetchInterval: followRunUnlessStreaming,
    ...liveQuery,
  })

  const pagesQuery = useQuery({
    queryKey: adminKeys.runPages(selectedRunId),
    queryFn: async () =>
      (
        await AdminService.readIngestionRunPages({
          path: { run_id: selectedRunId ?? "" },
        })
      ).data,
    enabled: Boolean(selectedRunId) && (onPagesTab || onReviewTab),
    refetchInterval: followRunUnlessStreaming,
    ...liveQuery,
  })

  const reviewsQuery = useQuery({
    queryKey: [
      ...adminKeys.reviews(),
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
    enabled: onReviewTab,
    refetchInterval: followWork(10_000),
    ...liveQuery,
  })

  useEffect(() => {
    const count = reviewsQuery.data?.count
    if (count !== undefined && reviewOffset > 0 && reviewOffset >= count) {
      setReviewOffset(Math.max(0, Math.floor((count - 1) / 100) * 100))
    }
  }, [reviewsQuery.data?.count, reviewOffset])

  const releasesQuery = useQuery({
    queryKey: adminKeys.releases(),
    queryFn: async () => (await AdminService.readCorpusReleases()).data,
    enabled: onReleasesTab || onBenchmarksTab,
    refetchInterval: followWork(5_000),
    ...liveQuery,
  })

  const benchmarkQuery = useQuery({
    queryKey: adminKeys.benchmark(selectedReleaseId),
    queryFn: async () =>
      (
        await AdminService.readEmbeddingBenchmark({
          path: { release_id: selectedReleaseId ?? "" },
        })
      ).data,
    enabled: Boolean(selectedReleaseId) && (onReleasesTab || onBenchmarksTab),
    refetchInterval: followWork(5_000),
    ...liveQuery,
  })

  const releaseManifestQuery = useQuery({
    queryKey: adminKeys.releaseManifest(selectedReleaseId),
    queryFn: async () =>
      (
        await AdminService.readReleaseManifest({
          path: { release_id: selectedReleaseId ?? "" },
        })
      ).data,
    enabled: Boolean(selectedReleaseId) && onReleasesTab,
    refetchInterval: followWork(5_000),
    retry: false,
    ...liveQuery,
  })

  const publicationEvidenceQuery = useQuery({
    queryKey: adminKeys.releaseEvidence(selectedReleaseId),
    queryFn: async () =>
      (
        await AdminService.readReleasePublicationEvidence({
          path: { release_id: selectedReleaseId ?? "" },
        })
      ).data,
    enabled: Boolean(selectedReleaseId) && onReleasesTab,
    refetchInterval: followWork(5_000),
    ...liveQuery,
  })

  // Roles change rarely and by an administrator's hand, so they are read when
  // the screen opens and again when the tab is returned to.
  const myRolesQuery = useQuery({
    queryKey: adminKeys.roles(),
    queryFn: async () => (await AdminService.readMyAdminRoles()).data,
    ...liveQuery,
  })

  const auditEventsQuery = useQuery({
    queryKey: adminKeys.auditEvents(selectedReleaseId),
    queryFn: async () =>
      (
        await AdminService.readAuditEvents({
          query: { entity_id: selectedReleaseId, limit: 50 },
        })
      ).data,
    enabled: Boolean(selectedReleaseId) && onReleasesTab,
    refetchInterval: followWork(10_000),
    ...liveQuery,
  })

  const myRoles = myRolesQuery.data?.roles ?? []
  const isSuperuser = Boolean(myRolesQuery.data?.is_superuser)
  const canUpload = isSuperuser || myRoles.includes("ingestion_uploader")
  const canReview = isSuperuser || myRoles.includes("legal_reviewer")
  const canPublish = isSuperuser || myRoles.includes("corpus_publisher")

  // A write refreshes only what it can have changed. The pipeline's own
  // follow-on work is picked up by the polling above.
  const refresh = (...keys: QueryKey[]) => {
    for (const queryKey of keys)
      void queryClient.invalidateQueries({ queryKey, exact: true })
  }
  const refreshReleases = (releaseId: string | undefined) => {
    refresh(adminKeys.releases(), adminKeys.metrics(), adminKeys.alerts())
    // The manifest, publication evidence and benchmark of this release.
    void queryClient.invalidateQueries({
      queryKey: adminKeys.release(releaseId),
    })
    refresh(adminKeys.auditEvents(releaseId), adminKeys.benchmark(releaseId))
  }

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
      refresh(adminKeys.runs(), adminKeys.metrics(), adminKeys.alerts())
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
      refresh(
        adminKeys.runs(),
        adminKeys.run(run.id),
        adminKeys.metrics(),
        adminKeys.alerts(),
      )
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
    onSuccess: (_result, { runId }) => {
      showSuccessToast("Page boundaries saved.")
      refresh(adminKeys.runs(), adminKeys.run(runId), adminKeys.metrics())
      void queryClient.invalidateQueries({
        queryKey: adminKeys.runPages(runId),
      })
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
      void queryClient.invalidateQueries({ queryKey: adminKeys.reviews() })
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
      void queryClient.invalidateQueries({ queryKey: adminKeys.reviews() })
      refresh(
        adminKeys.runs(),
        adminKeys.run(selectedRunId),
        adminKeys.metrics(),
        adminKeys.alerts(),
      )
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
      void queryClient.invalidateQueries({ queryKey: adminKeys.reviews() })
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
      refreshReleases(releaseId)
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
      refreshReleases(release.id)
      refresh(adminKeys.runs())
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

function alertToneClass(severity?: string | null): string {
  if (severity === "high") {
    return "border-[color:var(--legal-red)]/30 bg-[color:var(--legal-red-soft)] text-[color:var(--legal-red)]"
  }
  if (severity === "warning") {
    return "border-[color:var(--legal-amber)]/30 bg-[color:var(--legal-amber-soft)] text-[color:var(--legal-amber)]"
  }
  return "border-border bg-background text-foreground"
}
