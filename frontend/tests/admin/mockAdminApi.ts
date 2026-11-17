import type { Page, Route } from "@playwright/test"
import type {
  AdminMetrics,
  AdminOperationalAlertsPublic,
  AdminRole,
  AuditEventsPublic,
  CorpusReleaseManifestPublic,
  CorpusReleasePublic,
  CorpusReleasePublicationEvidencePublic,
  CorpusReleasePublishResponse,
  CorpusReleaseStatus,
  CorpusReleasesPublic,
  EmbeddingBenchmarkPublic,
  IngestionRunDetail,
  IngestionRunPublic,
  IngestionRunsPublic,
  MultipartPartsPublic,
  MyAdminRolesPublic,
  OcrBenchmarkPublic,
  PageSelectionUpdate,
  ReviewDecisionCreate,
  ReviewItemPublic,
  ReviewItemsPublic,
  SourceDocumentPublic,
  SourceDocumentVerificationRequest,
  SourcePagePublic,
  SourcePagesPublic,
  SourceUploadComplete,
  SourceUploadCompleteResponse,
  SourceUploadCreate,
  SourceUploadPublic,
  UserPublic,
} from "../../src/client"
import { userPublic } from "../fixtures/account.ts"
import { mockChatShell } from "../fixtures/shell.ts"
import { mockSignedIn } from "../utils/session.ts"
import {
  adminMetrics,
  adminUserId,
  auditEvent,
  candidateId,
  corpusRelease,
  corpusReleaseManifest,
  embeddingBenchmark,
  eventStreamBody,
  ingestionRun,
  ingestionRunDetail,
  ingestionRunFor,
  ingestionRuns,
  myAdminRoles,
  ocrBenchmark,
  operationalAlerts,
  type RunStage,
  releaseId,
  releasePublicationEvidence,
  reviewItem,
  runId,
  sourceDocument,
  sourceDocumentId,
  sourcePages,
  sourceUpload,
  type UploadOptions,
  uploadId,
} from "./fixtures.ts"

/** Reply with a JSON body of type `T`, so each response is checked against the API contract. */
export async function json<T>(route: Route, payload: T) {
  return route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(payload),
  })
}

/** The pages as the server returns them once the reviewer has confirmed the suggestions. */
function confirmedPages(pages: SourcePagePublic[]): SourcePagesPublic {
  return {
    data: pages.map((pageItem) => ({
      ...pageItem,
      inclusion_status:
        pageItem.inclusion_status === "suggested_exclude"
          ? "excluded"
          : "included",
    })),
    count: pages.length,
  }
}

/** A minimal one-page PDF that passes the browser's upload checks. */
export function onePagePdf() {
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 72] >>",
  ]
  let body = "%PDF-1.4\n"
  const offsets: number[] = []
  for (const [index, object] of objects.entries()) {
    offsets.push(Buffer.byteLength(body))
    body += `${index + 1} 0 obj\n${object}\nendobj\n`
  }
  const xrefOffset = Buffer.byteLength(body)
  body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`
  for (const offset of offsets) {
    body += `${String(offset).padStart(10, "0")} 00000 n \n`
  }
  body += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\n`
  body += `startxref\n${xrefOffset}\n%%EOF\n`
  return Buffer.from(body)
}

export async function installDroppingRunEventStream(page: Page) {
  await page.addInitScript(
    ({ runId }) => {
      const originalFetch = window.fetch.bind(window)
      const lastEventIds: Array<string | null> = []
      let requestCount = 0
      ;(
        window as unknown as {
          __adminSseLastEventIds?: Array<string | null>
        }
      ).__adminSseLastEventIds = lastEventIds

      const eventBody = (sequence: number, message: string) => {
        const payload = {
          id: `abababab-abab-4aba-8bab-abababababab-${sequence}`,
          run_id: runId,
          step_id: null,
          sequence,
          event_type: "stream_reconnected",
          stage: "profiling",
          message,
          payload: { request_number: sequence },
          created_at: new Date().toISOString(),
        }
        return `id: ${sequence}\nevent: stream_reconnected\ndata: ${JSON.stringify(payload)}\n\n`
      }

      window.fetch = async (input, init) => {
        const request =
          input instanceof Request ? input : new Request(input, init)
        const url = new URL(request.url, window.location.origin)
        if (
          !url.pathname.endsWith(`/api/v1/admin/ingestion-runs/${runId}/events`)
        ) {
          return originalFetch(input, init)
        }

        requestCount += 1
        lastEventIds.push(request.headers.get("Last-Event-ID"))
        const headers = {
          "Cache-Control": "no-cache",
          "Content-Type": "text/event-stream",
        }

        if (requestCount === 1) {
          const encoder = new TextEncoder()
          const stream = new ReadableStream({
            start(controller) {
              controller.enqueue(
                encoder.encode(
                  eventBody(1, "Initial streamed event before reconnect."),
                ),
              )
              setTimeout(
                () => controller.error(new Error("Dropped SSE connection")),
                0,
              )
            },
          })
          return new Response(stream, { headers, status: 200 })
        }

        return new Response(
          eventBody(2, "SSE stream resumed after reconnect."),
          { headers, status: 200 },
        )
      }
    },
    { runId },
  )
}

export async function runEventStreamLastEventIds(page: Page) {
  return page.evaluate(
    () =>
      (
        window as unknown as {
          __adminSseLastEventIds?: Array<string | null>
        }
      ).__adminSseLastEventIds ?? [],
  )
}

type AdminMockOptions = UploadOptions & {
  eventStream?: "ok" | "fail" | "fail-once"
  initialRunStage?: RunStage
  roles?: AdminRole[]
  isSuperuser?: boolean
}

export type AdminMockRequests = {
  completeExpectedVersion?: number
  completedParts: number
  detail: number
  eventStream: number
  multipartRequests: number
  pages: number
  pageSelectionBody?: Partial<PageSelectionUpdate>
  publicationEvidence: number
  r2Authorizations: number
  r2Puts: number
  releaseManifests: number
  runs: number
  sourceVerificationBody?: Partial<SourceDocumentVerificationRequest>
  sourceVerifications: number
  sourceUploadBody?: Partial<SourceUploadCreate>
}

/** Stub every admin API call, backed by the typed fixtures. */
export async function mockAdminApi(
  page: Page,
  options: AdminMockOptions = {},
): Promise<AdminMockRequests> {
  const requests: AdminMockRequests = {
    completedParts: 0,
    detail: 0,
    eventStream: 0,
    multipartRequests: 0,
    pages: 0,
    publicationEvidence: 0,
    r2Authorizations: 0,
    r2Puts: 0,
    releaseManifests: 0,
    runs: 0,
    sourceVerifications: 0,
  }
  let sourceVerified = false
  let releaseStatus: CorpusReleaseStatus = "validating"
  let revisionText: string | null = null

  await mockSignedIn(page, "playwright-admin-token")
  // The shared sidebar reads chat history. Keep its fake bearer token away
  // from the live API, where a 401 would sign this mocked admin out.
  await mockChatShell(page)
  await page.route("**/api/v1/users/me", async (route) =>
    json<UserPublic>(
      route,
      userPublic({
        id: adminUserId,
        email: "admin@example.test",
        full_name: "Legal Admin",
        is_superuser: true,
      }),
    ),
  )
  await page.route("https://r2.example.test/**", async (route) => {
    if (route.request().method() === "OPTIONS") {
      return route.fulfill({
        status: 204,
        headers: {
          "Access-Control-Allow-Headers": "*",
          "Access-Control-Allow-Methods": "PUT,OPTIONS",
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Expose-Headers": "etag",
        },
      })
    }
    requests.r2Puts += 1
    const headers = route.request().headers()
    if (headers.authorization) {
      requests.r2Authorizations += 1
    }
    return route.fulfill({
      status: 200,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Expose-Headers": "etag",
        etag: `"etag-${requests.r2Puts}"`,
      },
    })
  })
  await page.route("**/api/v1/admin/**", async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === "GET" && path.endsWith("/metrics")) {
      return json<AdminMetrics>(route, adminMetrics())
    }

    if (method === "GET" && path.endsWith("/alerts")) {
      const alerts = operationalAlerts()
      return json<AdminOperationalAlertsPublic>(route, {
        data: alerts,
        count: alerts.length,
      })
    }

    if (method === "GET" && path.endsWith("/ingestion-runs")) {
      const runs = ingestionRuns(options.initialRunStage)
      requests.runs += 1
      return json<IngestionRunsPublic>(route, {
        data: runs,
        count: runs.length,
      })
    }

    const runEventsMatch = path.match(/\/ingestion-runs\/([^/]+)\/events$/)
    if (method === "GET" && runEventsMatch) {
      requests.eventStream += 1
      const eventStream = options.eventStream ?? "ok"
      if (
        eventStream === "fail" ||
        (eventStream === "fail-once" && requests.eventStream === 1)
      ) {
        return route.fulfill({ status: 503, body: "stream unavailable" })
      }
      return route.fulfill({
        status: 200,
        headers: {
          "Cache-Control": "no-cache",
          "Content-Type": "text/event-stream",
        },
        body: eventStreamBody(runEventsMatch[1], requests.eventStream),
      })
    }

    const runPagesMatch = path.match(/\/ingestion-runs\/([^/]+)\/pages$/)
    if (method === "GET" && runPagesMatch) {
      requests.pages += 1
      const pages = sourcePages(runPagesMatch[1])
      return json<SourcePagesPublic>(route, {
        data: pages,
        count: pages.length,
      })
    }

    if (method === "PATCH" && runPagesMatch)
      return json<SourcePagesPublic>(
        route,
        confirmedPages(sourcePages(runPagesMatch[1])),
      )

    const runDetailMatch = path.match(/\/ingestion-runs\/([^/]+)$/)
    if (method === "GET" && runDetailMatch) {
      requests.detail += 1
      return json<IngestionRunDetail>(
        route,
        ingestionRunDetail(runDetailMatch[1], options.initialRunStage),
      )
    }

    const retryMatch = path.match(/\/ingestion-runs\/([^/]+)\/retry$/)
    if (method === "POST" && retryMatch) {
      return json<IngestionRunPublic>(route, {
        ...ingestionRunFor(retryMatch[1], options.initialRunStage),
        status: "queued",
      })
    }

    const cancelMatch = path.match(/\/ingestion-runs\/([^/]+)\/cancel$/)
    if (method === "POST" && cancelMatch) {
      return json<IngestionRunPublic>(route, {
        ...ingestionRunFor(cancelMatch[1], options.initialRunStage),
        status: "cancelled",
      })
    }

    const resumeMatch = path.match(/\/ingestion-runs\/([^/]+)\/resume$/)
    if (method === "POST" && resumeMatch) {
      return json<IngestionRunPublic>(route, {
        ...ingestionRunFor(resumeMatch[1], options.initialRunStage),
        status: "queued",
      })
    }

    if (method === "POST" && path.endsWith("/source-uploads")) {
      requests.sourceUploadBody =
        request.postDataJSON() as Partial<SourceUploadCreate>
      return json<SourceUploadPublic>(
        route,
        sourceUpload(options, requests.sourceUploadBody),
      )
    }

    if (
      method === "PUT" &&
      path.endsWith(`/source-uploads/${uploadId}/object`)
    ) {
      return route.fulfill({ status: 204 })
    }

    if (
      method === "POST" &&
      path.endsWith(`/source-uploads/${uploadId}/multipart-parts`)
    ) {
      requests.multipartRequests += 1
      return json<MultipartPartsPublic>(route, {
        upload_id: uploadId,
        multipart_upload_id: "browser-multipart-1",
        parts: [
          {
            part_number: 1,
            upload_url: `https://r2.example.test/quarantine/${uploadId}/constitution.pdf?partNumber=1`,
          },
        ],
      })
    }

    if (
      method === "POST" &&
      path.endsWith(`/source-uploads/${uploadId}/complete`)
    ) {
      const completeBody =
        request.postDataJSON() as Partial<SourceUploadComplete>
      requests.completeExpectedVersion = completeBody.expected_version
      requests.completedParts = completeBody.completed_parts?.length ?? 0
      return json<SourceUploadCompleteResponse>(route, {
        upload: {
          ...sourceUpload(options, requests.sourceUploadBody),
          status: "completed",
          lock_version: 3,
        },
        source_document: sourceDocument(
          options,
          requests.sourceUploadBody,
          sourceVerified,
        ),
        run: ingestionRun(),
        duplicate: false,
      })
    }

    if (
      method === "POST" &&
      path.endsWith(`/source-documents/${sourceDocumentId}/verify`)
    ) {
      requests.sourceVerifications += 1
      requests.sourceVerificationBody =
        request.postDataJSON() as Partial<SourceDocumentVerificationRequest>
      sourceVerified = true
      return json<SourceDocumentPublic>(
        route,
        sourceDocument(options, undefined, sourceVerified),
      )
    }

    const pageSelectionMatch = path.match(
      /\/ingestion-runs\/([^/]+)\/page-selection$/,
    )
    if (method === "PATCH" && pageSelectionMatch) {
      requests.pageSelectionBody =
        request.postDataJSON() as Partial<PageSelectionUpdate>
      return json<SourcePagesPublic>(
        route,
        confirmedPages(sourcePages(pageSelectionMatch[1])),
      )
    }

    if (method === "GET" && path.endsWith("/review-items")) {
      return json<ReviewItemsPublic>(route, {
        data: [reviewItem(sourceVerified, revisionText)],
        count: 1,
      })
    }

    if (method === "PATCH" && path.endsWith(`/review-items/${candidateId}`)) {
      revisionText =
        "The privacy of citizens is hereby guaranteed and protected."
      return json<ReviewItemPublic>(route, {
        ...reviewItem(sourceVerified, revisionText),
        revision_number: 2,
      })
    }

    if (
      method === "POST" &&
      path.endsWith(`/review-items/${candidateId}/decision`)
    ) {
      const body = request.postDataJSON() as Partial<ReviewDecisionCreate>
      return json<ReviewItemPublic>(route, {
        ...reviewItem(sourceVerified, revisionText),
        status:
          body.decision === "approve"
            ? "approved"
            : body.decision === "reject"
              ? "rejected"
              : "needs_review",
        decisions: [
          {
            id: "77777777-7777-4777-8777-777777777777",
            candidate_id: candidateId,
            decided_by: adminUserId,
            decision: body.decision ?? "approve",
            reason: body.reason ?? "Checked against source coordinates.",
            created_at: new Date().toISOString(),
          },
        ],
      })
    }

    if (method === "GET" && path.endsWith("/corpus-releases")) {
      return json<CorpusReleasesPublic>(route, {
        data: [corpusRelease({ status: releaseStatus })],
        count: 1,
      })
    }

    if (
      method === "GET" &&
      path.endsWith(`/corpus-releases/${releaseId}/manifest`)
    ) {
      requests.releaseManifests += 1
      return json<CorpusReleaseManifestPublic>(route, corpusReleaseManifest())
    }

    if (
      method === "GET" &&
      path.endsWith(`/corpus-releases/${releaseId}/publication-evidence`)
    ) {
      requests.publicationEvidence += 1
      return json<CorpusReleasePublicationEvidencePublic>(
        route,
        releasePublicationEvidence(),
      )
    }

    if (
      method === "GET" &&
      path.endsWith(`/embedding-benchmarks/${releaseId}`)
    ) {
      return json<EmbeddingBenchmarkPublic>(route, embeddingBenchmark())
    }

    if (
      method === "POST" &&
      path.endsWith(`/corpus-releases/${releaseId}/validate`)
    ) {
      releaseStatus = "approved"
      return json<CorpusReleasePublic>(
        route,
        corpusRelease({ status: "approved" }),
      )
    }

    if (
      method === "POST" &&
      path.endsWith(`/corpus-releases/${releaseId}/publish`)
    ) {
      releaseStatus = "production"
      return json<CorpusReleasePublishResponse>(route, {
        release: corpusRelease({ status: "production" }),
        promotion_status: "succeeded",
        vector_index_status: "promoted",
      })
    }

    if (method === "GET" && path.endsWith("/my-roles")) {
      return json<MyAdminRolesPublic>(
        route,
        myAdminRoles({
          is_superuser: options.isSuperuser ?? true,
          roles: options.roles ?? [
            "ingestion_uploader",
            "legal_reviewer",
            "corpus_publisher",
          ],
        }),
      )
    }

    if (method === "GET" && path.includes("/audit-events")) {
      return json<AuditEventsPublic>(route, {
        data: [auditEvent()],
        count: 1,
      })
    }

    if (method === "GET" && path.includes("/ocr-benchmarks/")) {
      return json<OcrBenchmarkPublic>(route, ocrBenchmark())
    }

    return route.fulfill({ status: 404, body: `No mock for ${method} ${path}` })
  })

  return requests
}
