import { useEffect, useState } from "react"
import { FiCheckCircle, FiSearch } from "react-icons/fi"
import type {
  CompositeReleaseCreate,
  CorpusReleaseManifestPublic,
  CorpusReleasePublic,
  CorpusReleasePublicationEvidencePublic,
  EmbeddingBenchmarkPublic,
} from "@/client"
import { ComposeReleaseForm } from "@/components/Constitution/admin/ComposeReleaseForm"
import {
  formatCurrency,
  formatDateTime,
  formatMetric,
  formatPercent,
  labelize,
} from "@/components/Constitution/admin/format"
import { releaseManifestSummary } from "@/components/Constitution/admin/release-manifest"
import {
  EmptyState,
  FieldLabel,
  ListState,
  Panel,
  SmallStat,
  StatusPill,
} from "@/components/Constitution/admin/ui"
import { SquircleButton } from "@/components/Constitution/primitives"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

// Publishing replaces the whole live corpus, so only a release that contains
// the Constitution can go live; an Act-only release is a member to compose.
function containsConstitution(release: CorpusReleasePublic) {
  return release.instrument_types?.includes("constitution") ?? false
}

export function ReleaseWorkspace({
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
                    : "pgvector index build"}
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
