import type {
  AdminMetrics,
  AdminOperationalAlertPublic,
  AuditEventPublic,
  CorpusReleaseManifestPublic,
  CorpusReleasePublic,
  CorpusReleasePublicationEvidencePublic,
  EmbeddingBenchmarkPublic,
  IngestionEventPublic,
  IngestionRunDetail,
  IngestionRunPublic,
  IngestionStage,
  MyAdminRolesPublic,
  OcrBenchmarkPublic,
  ReviewIssuePublic,
  ReviewItemPublic,
  SourceDocumentPublic,
  SourcePagePublic,
  SourceUploadCreate,
  SourceUploadPublic,
} from "../../src/client"

// Typed bodies for the admin endpoints. Values follow what the current server
// produces (`backend/app/ingestion/service.py` and `worker.py`): parser and
// extractor versions, pgvector index builds, the shape of the release manifest
// and of operational alerts. A field that is renamed, removed or newly required
// in the API fails the type-check here.

export const runId = "11111111-1111-4111-8111-111111111111"
export const failedRunId = "11111111-1111-4111-8111-222222222222"
export const cancelledRunId = "11111111-1111-4111-8111-333333333333"
export const sourceDocumentId = "22222222-2222-4222-8222-222222222222"
export const candidateId = "33333333-3333-4333-8333-333333333333"
export const releaseId = "44444444-4444-4444-8444-444444444444"
export const uploadId = "55555555-5555-4555-8555-555555555555"
export const adminUserId = "99999999-9999-4999-8999-999999999999"

const issueId = "12121212-1212-4121-8121-121212121212"
const embeddingRunId = "93939393-9393-4393-9393-939393939393"
const profileId = "88888888-8888-4888-8888-888888888888"
export const retrievalIndexBuildId = "92929292-9292-4292-9292-929292929292"
const promotionAttemptId = "94949494-9494-4494-9494-949494949494"
const stepIds = {
  uploading: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  confirmation: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
}
const taskId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"

export const constitutionParserVersion = "constitution-hierarchy-v4"
export const nativeExtractorVersion = "pypdf-native-layout-v2"
export const sectionPath = "constitution-1999.chapter4.section37"

export type RunStage = Extract<
  IngestionStage,
  "awaiting_page_confirmation" | "verifying_upload"
>

export type UploadOptions = {
  multipartRequired?: boolean
  uploadBackend?: "local" | "r2"
}

const now = () => new Date().toISOString()

export function adminMetrics(): AdminMetrics {
  return {
    active_runs: 1,
    blocked_runs: 1,
    failed_runs: 1,
    queue_depth: 2,
    worker_heartbeat: now(),
    pages_processed: 2,
    ocr_fallback_rate: 0.5,
    review_issues: 1,
    auto_approval_rate: 0.25,
    embedding_progress: 0.5,
    current_production_release: "2026.09.test",
  }
}

export function myAdminRoles(
  overrides: Partial<MyAdminRolesPublic> = {},
): MyAdminRolesPublic {
  return {
    user_id: adminUserId,
    is_superuser: true,
    roles: ["ingestion_uploader", "legal_reviewer", "corpus_publisher"],
    ...overrides,
  }
}

export function auditEvent(
  overrides: Partial<AuditEventPublic> = {},
): AuditEventPublic {
  return {
    id: "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa",
    actor_user_id: adminUserId,
    action: "corpus_release.publish",
    entity_type: "corpus_release",
    entity_id: releaseId,
    severity: "info",
    reason: "Browser test audit entry.",
    payload: {},
    created_at: now(),
    ...overrides,
  }
}

export function ocrBenchmark(): OcrBenchmarkPublic {
  return {
    dataset_version: "ocr-gold-v1",
    sample_count: 2,
    winner: "google_document_ai",
    providers: [
      {
        provider: "google_document_ai",
        page_count: 2,
        failure_count: 0,
        mean_character_accuracy: 0.99,
        mean_confidence: 0.95,
        total_cost_usd: 0.04,
        mean_timing_ms: 1200,
      },
    ],
    active_dataset_items: 2,
  }
}

export function embeddingBenchmark(): EmbeddingBenchmarkPublic {
  return {
    release_id: releaseId,
    results: [
      {
        profile_id: profileId,
        provider: "openai",
        model_name: "text-embedding-3-large",
        status: "succeeded",
        recall_at_10: 0.96,
        ndcg_at_10: 0.94,
        cost_usd: 1.25,
        p95_latency_ms: 310,
        selected_for_release: true,
        metrics: { smoke_queries_passed: true },
      },
    ],
  }
}

export function ingestionRun(
  initialRunStage: RunStage = "verifying_upload",
): IngestionRunPublic {
  return {
    id: runId,
    source_upload_id: uploadId,
    source_document_id: sourceDocumentId,
    created_by: adminUserId,
    status: "waiting_for_input",
    current_stage: initialRunStage,
    pipeline_version: "legal-ingestion-v1",
    pipeline_config: { instrument_parser: "constitution" },
    expected_page_count: 2,
    total_units: 2,
    completed_units: 1,
    failed_units: 0,
    lock_version: 4,
    error_details: null,
    created_at: now(),
    updated_at: now(),
    completed_at: null,
  }
}

export function failedIngestionRun(
  initialRunStage: RunStage = "verifying_upload",
): IngestionRunPublic {
  return {
    ...ingestionRun(initialRunStage),
    id: failedRunId,
    status: "failed",
    current_stage: "native_extraction",
    completed_units: 0,
    failed_units: 1,
    error_details: { message: "Native extraction worker failed." },
    lock_version: 7,
  }
}

export function cancelledIngestionRun(
  initialRunStage: RunStage = "verifying_upload",
): IngestionRunPublic {
  return {
    ...ingestionRun(initialRunStage),
    id: cancelledRunId,
    status: "cancelled",
    current_stage: "publishing",
    completed_units: 1,
    failed_units: 0,
    lock_version: 9,
  }
}

export function ingestionRuns(
  initialRunStage: RunStage = "verifying_upload",
): IngestionRunPublic[] {
  return [
    ingestionRun(initialRunStage),
    failedIngestionRun(initialRunStage),
    cancelledIngestionRun(initialRunStage),
  ]
}

export function ingestionRunFor(
  id: string,
  initialRunStage: RunStage = "verifying_upload",
): IngestionRunPublic {
  return (
    ingestionRuns(initialRunStage).find((run) => run.id === id) ??
    ingestionRun(initialRunStage)
  )
}

export function ingestionRunDetail(
  id = runId,
  initialRunStage: RunStage = "verifying_upload",
): IngestionRunDetail {
  return {
    ...ingestionRunFor(id, initialRunStage),
    steps: [
      {
        id: stepIds.uploading,
        run_id: id,
        dependency_step_id: null,
        stage: "uploading",
        status: "succeeded",
        attempt_count: 1,
        lease_owner: null,
        leased_until: null,
        heartbeat_at: null,
        total_units: 1,
        completed_units: 1,
        failed_units: 0,
        lock_version: 1,
        started_at: now(),
        completed_at: now(),
        metrics: null,
        error_details: null,
        created_at: now(),
        updated_at: now(),
      },
      {
        id: stepIds.confirmation,
        run_id: id,
        dependency_step_id: stepIds.uploading,
        stage: "awaiting_page_confirmation",
        status: "blocked",
        attempt_count: 1,
        lease_owner: null,
        leased_until: null,
        heartbeat_at: null,
        total_units: 2,
        completed_units: 1,
        failed_units: 0,
        lock_version: 1,
        started_at: now(),
        completed_at: null,
        metrics: { pages_profiled: 2 },
        error_details: null,
        created_at: now(),
        updated_at: now(),
      },
    ],
    events: [
      {
        id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        run_id: id,
        step_id: null,
        sequence: 1,
        event_type: "upload_completed",
        stage: "verifying_upload",
        message: "Upload validated and ingestion run queued",
        payload: { page_count: 2 },
        created_at: now(),
      },
    ],
    tasks: [
      {
        id: taskId,
        run_id: id,
        step_id: stepIds.confirmation,
        task_type: "awaiting_page_confirmation",
        status: "pending",
        priority: 10,
        attempt_count: 1,
        max_attempts: 3,
        lease_owner: null,
        leased_until: null,
        heartbeat_at: null,
        lock_version: 1,
        payload: { page_count: 2 },
        error_details: null,
        created_at: now(),
        updated_at: now(),
      },
    ],
  }
}

export function streamedRunEvent(
  id: string,
  requestNumber: number,
): IngestionEventPublic {
  return {
    id: "abababab-abab-4aba-8bab-abababababab",
    run_id: id,
    step_id: null,
    sequence: requestNumber,
    event_type: "stream_reconnected",
    stage: "profiling",
    message: "SSE stream resumed after reconnect.",
    payload: { request_number: requestNumber },
    created_at: now(),
  }
}

/** The body of the `ingestion_event` stream for one connection. */
export function eventStreamBody(id: string, requestNumber: number) {
  return [
    `id: ${requestNumber}`,
    "event: ingestion_event",
    `data: ${JSON.stringify(streamedRunEvent(id, requestNumber))}`,
    "",
    "",
  ].join("\n")
}

export function sourcePages(id = runId): SourcePagePublic[] {
  return [
    {
      id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      run_id: id,
      source_document_id: sourceDocumentId,
      page_number: 1,
      role: "front_matter",
      inclusion_status: "suggested_exclude",
      inclusion_reason: "cover page",
      thumbnail_key: "thumbs/1.webp",
      text_density: 0.1,
      orientation: "portrait",
      column_count: 1,
      image_coverage: 0.8,
      width: 612,
      height: 792,
      quality_signals: {
        likely_cover: true,
        preview_text: "Cover page for the official Constitution source.",
      },
      lock_version: 1,
      created_at: now(),
    },
    {
      id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
      run_id: id,
      source_document_id: sourceDocumentId,
      page_number: 2,
      role: "legal_body",
      inclusion_status: "suggested_include",
      inclusion_reason: "legal text",
      thumbnail_key: "thumbs/2.webp",
      text_density: 0.92,
      orientation: "portrait",
      column_count: 1,
      image_coverage: 0.02,
      width: 612,
      height: 792,
      quality_signals: {
        detected_provisions: ["Section 37"],
        headers_removed: false,
        preview_text:
          "Section 37. The privacy of citizens is hereby guaranteed.",
      },
      lock_version: 1,
      created_at: now(),
    },
  ]
}

export function sourceDocument(
  options: UploadOptions = {},
  body?: Partial<SourceUploadCreate>,
  verified = false,
): SourceDocumentPublic {
  return {
    id: sourceDocumentId,
    legal_instrument_id: "66666666-6666-4666-8666-666666666666",
    authority: "Official Gazette",
    title: "Browser PDF source",
    source_url: "https://example.test/cfrn.pdf",
    mime_type: "application/pdf",
    sha256: "a".repeat(64),
    storage_backend: options.uploadBackend ?? "local",
    storage_bucket: null,
    storage_key: `sources/sha256/${"a".repeat(64)}/original.pdf`,
    original_filename: "constitution.pdf",
    file_size: 512,
    page_count: 1,
    published_at: "1999-05-29",
    retrieved_at: now(),
    source_tier: "official",
    is_legal_revision: body?.is_legal_revision ?? false,
    legal_revision_effective_at: body?.legal_revision_effective_at ?? null,
    parser_version: constitutionParserVersion,
    verification_status: verified ? "verified" : "unverified",
    created_by: adminUserId,
    verified_by: verified ? adminUserId : null,
    verified_at: verified ? now() : null,
    lock_version: verified ? 2 : 1,
    created_at: now(),
  }
}

export function sourceUpload(
  options: UploadOptions = {},
  body?: Partial<SourceUploadCreate>,
): SourceUploadPublic {
  const uploadBackend = options.uploadBackend ?? "local"
  const multipartRequired = options.multipartRequired ?? false
  const quarantineKey = `quarantine/${uploadId}/constitution.pdf`
  return {
    id: uploadId,
    idempotency_key: "upload-browser-test",
    source_document_id: null,
    instrument_slug: "constitution-1999",
    instrument_title: "Constitution of the Federal Republic of Nigeria 1999",
    instrument_type: "constitution",
    source_title: "Browser PDF source",
    authority: "Official Gazette",
    source_url: "https://example.test/cfrn.pdf",
    source_tier: "official",
    is_legal_revision: body?.is_legal_revision ?? false,
    legal_revision_effective_at: body?.legal_revision_effective_at ?? null,
    original_filename: "constitution.pdf",
    mime_type: "application/pdf",
    expected_size: 512,
    expected_sha256: "a".repeat(64),
    actual_sha256: null,
    upload_backend: uploadBackend,
    quarantine_key: quarantineKey,
    canonical_key: null,
    upload_url:
      uploadBackend === "r2"
        ? multipartRequired
          ? ""
          : `https://r2.example.test/${quarantineKey}?signed=put`
        : `/api/v1/admin/source-uploads/${uploadId}/object`,
    upload_headers:
      uploadBackend === "r2"
        ? {
            "content-type": "application/pdf",
            "x-amz-meta-source-upload-id": uploadId,
            "x-amz-meta-sha256": "a".repeat(64),
          }
        : { "content-type": "application/pdf" },
    multipart_required: multipartRequired,
    status: "created",
    error_message: null,
    lock_version: 1,
    expires_at: now(),
    completed_at: null,
    created_at: now(),
    updated_at: now(),
  }
}

export function reviewIssue(
  overrides: Partial<ReviewIssuePublic> = {},
): ReviewIssuePublic {
  return {
    id: issueId,
    candidate_id: candidateId,
    issue_type: "source_span_coverage",
    severity: "blocking",
    status: "open",
    blocking: true,
    message: "Candidate requires source-span verification.",
    evidence: { page: 2 },
    created_at: now(),
    ...overrides,
  }
}

export function reviewItem(
  sourceVerified = false,
  latestRevisionText: string | null = null,
): ReviewItemPublic & { issues: ReviewIssuePublic[] } {
  return {
    id: candidateId,
    run_id: runId,
    source_document_id: sourceDocumentId,
    source_document: sourceDocument({}, undefined, sourceVerified),
    parent_candidate_id: null,
    materialized_provision_id: null,
    materialized_version_id: null,
    kind: "section",
    number: "37",
    heading: "Right to private and family life",
    canonical_path: sectionPath,
    sort_key: "004.037",
    raw_text: "The privacy of citizens is hereby guaranteed.",
    latest_revision_text: latestRevisionText,
    normalized_text: "the privacy of citizens is hereby guaranteed.",
    source_page_start: 2,
    source_page_end: 2,
    source_spans: [{ page: 2, bbox: [72, 120, 520, 180] }],
    ancestor_headings: ["Chapter IV", "Fundamental Rights"],
    parser_version: constitutionParserVersion,
    extractor_version: nativeExtractorVersion,
    parser_confidence: 0.81,
    extractor_confidence: 0.9,
    status: "needs_review",
    blocking_issue_count: 1,
    revision_number: 1,
    lock_version: 2,
    issues: [reviewIssue()],
    revisions: [],
    decisions: [],
    created_at: now(),
    updated_at: now(),
  }
}

export function corpusRelease(
  overrides: Partial<CorpusReleasePublic> = {},
): CorpusReleasePublic {
  return {
    id: releaseId,
    version: "2026.09.test",
    status: "validating",
    source_manifest_hash: "b".repeat(64),
    embedding_model: "text-embedding-3-large",
    embedding_model_version: "pinned",
    parser_version: constitutionParserVersion,
    validation_report: { unresolved_gates: [] },
    approved_by: null,
    approved_at: null,
    lock_version: 3,
    created_at: now(),
    evidence_count: 1,
    instrument_slugs: ["constitution-1999"],
    instrument_types: ["constitution"],
    ...overrides,
  }
}

export function corpusReleaseManifest(): CorpusReleaseManifestPublic {
  return {
    release_id: releaseId,
    release_version: "2026.09.test",
    source_manifest_hash: "b".repeat(64),
    artifact: {
      id: "90909090-9090-4090-9090-909090909090",
      run_id: runId,
      artifact_type: "release_manifest",
      storage_key: "artifacts/release-manifest.json",
      sha256: "c".repeat(64),
      mime_type: "application/json",
      retention_policy: "retain_indefinitely",
      artifact_metadata: {
        release_id: releaseId,
        source_manifest_hash: "b".repeat(64),
      },
      created_at: now(),
    },
    // The manifest the worker writes (`_release_manifest` in the ingestion
    // worker): source documents keyed by `source_document_id`, and one entry
    // per provision version.
    manifest: {
      manifest_version: 1,
      release_id: releaseId,
      release_version: "2026.09.test",
      materialized_run_id: runId,
      ingestion_run_ids: [runId],
      source_document_ids: [sourceDocumentId],
      source_documents: [
        {
          source_document_id: sourceDocumentId,
          title: "Official 1999 Constitution PDF",
          authority: "Official Gazette",
          source_url: "https://example.test/cfrn.pdf",
          sha256: "a".repeat(64),
          storage_key: `sources/sha256/${"a".repeat(64)}/original.pdf`,
          published_at: "1999-05-29",
          retrieved_at: now(),
          verification_status: "verified",
          is_legal_revision: false,
          legal_revision_effective_at: null,
        },
      ],
      entries: [
        {
          canonical_path: sectionPath,
          provision_id: "95959595-9595-4595-9595-959595959595",
          provision_version_id: "91919191-9191-4191-9191-919191919191",
          text_sha256: "f".repeat(64),
          source_document_id: sourceDocumentId,
          source_page_start: 2,
          source_page_end: 2,
        },
      ],
    },
  }
}

/**
 * Publication evidence for a release published to the pgvector target. The
 * server no longer creates `vector_indexes`, rolled-back attempts or collection
 * names; it records a ready index build and a succeeded promotion attempt.
 */
export function releasePublicationEvidence(): CorpusReleasePublicationEvidencePublic {
  return {
    release_id: releaseId,
    release_version: "2026.09.test",
    vector_indexes: [],
    retrieval_index_builds: [
      {
        id: retrievalIndexBuildId,
        release_id: releaseId,
        embedding_run_id: embeddingRunId,
        profile_id: profileId,
        backend: "pgvector",
        index_kind: "enacted",
        relation_name: "retrieval_embedding",
        physical_index_name: null,
        status: "ready",
        expected_segment_count: 1,
        stored_segment_count: 1,
        stored_embedding_count: 1,
        vector_dimensions: 1024,
        profile_hash: "d".repeat(64),
        payload_schema_hash: "d".repeat(64),
        checksum: "e".repeat(64),
        validation_report: { is_valid: true },
        created_at: now(),
        updated_at: now(),
      },
    ],
    promotion_attempts: [
      {
        id: promotionAttemptId,
        release_id: releaseId,
        vector_index_id: null,
        retrieval_index_build_id: retrievalIndexBuildId,
        index_kind: "enacted",
        requested_by: adminUserId,
        status: "succeeded",
        previous_release_id: null,
        previous_collection_name: null,
        target_collection_name: null,
        rollback_completed: false,
        error_details: null,
        started_at: now(),
        completed_at: now(),
        created_at: now(),
      },
    ],
    active_targets: [],
    actor_separation: {
      current_actor_id: adminUserId,
      source_uploader_ids: [adminUserId],
      current_actor_is_source_uploader: true,
      approved_by: null,
      approved_by_differs_from_uploaders: null,
      superuser_override_recorded: true,
      override_reasons: ["Two-person override recorded in browser test."],
    },
  }
}

/** The text the server shows for a failed promotion that recorded no message. */
export const publicationFailureMessage =
  "Corpus release publication failed before promotion completed."

/** One alert of each type `read_admin_operational_alerts` can raise. */
export function operationalAlerts(): AdminOperationalAlertPublic[] {
  const detectedAt = now()
  return [
    {
      id: `run-failed:${failedRunId}`,
      alert_type: "terminal_failure",
      severity: "high",
      title: "Terminal ingestion failure",
      message: "Native extraction worker failed.",
      detected_at: detectedAt,
      run_id: failedRunId,
      evidence: {
        status: "failed",
        stage: "native_extraction",
        error_details: { message: "Native extraction worker failed." },
      },
    },
    {
      id: `stalled-lease:${taskId}`,
      alert_type: "stalled_lease",
      severity: "warning",
      title: "Stalled worker lease",
      message: "native_extraction lease expired for worker-browser-test.",
      detected_at: detectedAt,
      run_id: runId,
      step_id: stepIds.confirmation,
      task_id: taskId,
      evidence: {
        task_type: "native_extraction",
        status: "running",
        lease_owner: "worker-browser-test",
        leased_until: detectedAt,
        heartbeat_at: null,
      },
    },
    {
      id: `blocking-review-issue:${issueId}`,
      alert_type: "unresolved_blocking_issue",
      severity: "high",
      title: "Unresolved blocking review issue",
      message: "Candidate requires source-span verification.",
      detected_at: detectedAt,
      run_id: runId,
      candidate_id: candidateId,
      issue_id: issueId,
      evidence: {
        issue_type: "source_span_coverage",
        severity: "blocking",
        candidate_path: sectionPath,
        evidence: { page: 2 },
      },
    },
    {
      id: `embedding-provider-outage:${embeddingRunId}`,
      alert_type: "embedding_provider_outage",
      severity: "high",
      title: "Embedding provider outage",
      message: "HF TEI endpoint returned 502.",
      detected_at: detectedAt,
      release_id: releaseId,
      embedding_run_id: embeddingRunId,
      evidence: {
        profile_id: profileId,
        benchmark_dataset_version: "browser-gold-v1",
        error_details: { message: "HF TEI endpoint returned 502." },
      },
    },
    {
      id: `publication-failed:${promotionAttemptId}`,
      alert_type: "publication_failure",
      severity: "high",
      title: "Publication failure",
      message: publicationFailureMessage,
      detected_at: detectedAt,
      release_id: releaseId,
      promotion_attempt_id: promotionAttemptId,
      evidence: {
        vector_index_id: null,
        previous_release_id: null,
        target_collection_name: null,
        rollback_completed: false,
        error_details: null,
      },
    },
  ]
}
