import { expect, type Page, type Route, test } from "@playwright/test"

const runId = "11111111-1111-4111-8111-111111111111"
const failedRunId = "11111111-1111-4111-8111-222222222222"
const cancelledRunId = "11111111-1111-4111-8111-333333333333"
const sourceDocumentId = "22222222-2222-4222-8222-222222222222"
const candidateId = "33333333-3333-4333-8333-333333333333"
const releaseId = "44444444-4444-4444-8444-444444444444"
const uploadId = "55555555-5555-4555-8555-555555555555"

test.use({ storageState: { cookies: [], origins: [] } })

test("Admin legal workspace is accessible and shows evidence operations", async ({
  page,
}) => {
  await mockAdminApi(page)

  await page.goto("/admin")

  await expect(
    page.getByRole("heading", { name: "Review the evidence layer." }),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Upload source" }),
  ).toBeVisible()

  for (const tab of [
    "Ingestion runs",
    "Page boundaries",
    "Review queue",
    "Corpus releases",
    "Benchmarks",
  ]) {
    await expect(page.getByRole("tab", { name: tab })).toBeVisible()
  }
})

test("Admin can complete a PDF upload session from the browser", async ({
  page,
}) => {
  await mockAdminApi(page)

  await page.goto("/admin")
  await page.getByRole("button", { name: "Upload source" }).click()

  await page.getByLabel("Instrument slug").fill(`cfrn-1999-${Date.now()}`)
  await page.getByLabel("Source title").fill("Browser PDF source")
  await page.getByLabel("Source URL").fill("https://example.test/cfrn.pdf")
  await page.getByLabel("Source file").setInputFiles({
    name: "constitution.pdf",
    mimeType: "application/pdf",
    buffer: onePagePdf(),
  })
  await page.getByRole("button", { name: "Start ingestion" }).click()

  await expect(
    page.getByText("Source upload completed and ingestion queued."),
  ).toBeVisible()
  await expect(page.getByText("Verifying Upload").first()).toBeVisible()
})

test("Admin can classify an upload as a legal revision source", async ({
  page,
}) => {
  const requests = await mockAdminApi(page)

  await page.goto("/admin")
  await page.getByRole("button", { name: "Upload source" }).click()

  await page
    .getByLabel("Instrument slug")
    .fill(`cfrn-1999-revision-${Date.now()}`)
  await page.getByLabel("Source title").fill("Fifth Alteration source")
  await page
    .getByLabel("Source URL")
    .fill("https://example.test/cfrn-fifth-alteration.pdf")
  await page.getByRole("checkbox", { name: "Legal revision" }).click()
  await page.getByLabel("Revision effective date").fill("2026-01-01")
  await page.getByLabel("Source file").setInputFiles({
    name: "constitution-amendment.pdf",
    mimeType: "application/pdf",
    buffer: onePagePdf(),
  })
  await page.getByRole("button", { name: "Start ingestion" }).click()

  await expect(
    page.getByText("Source upload completed and ingestion queued."),
  ).toBeVisible()
  expect(requests.sourceUploadBody?.is_legal_revision).toBe(true)
  expect(requests.sourceUploadBody?.legal_revision_effective_at).toBe(
    "2026-01-01",
  )
})

test("Admin must set an effective date for legal revision uploads", async ({
  page,
}) => {
  const requests = await mockAdminApi(page)

  await page.goto("/admin")
  await page.getByRole("button", { name: "Upload source" }).click()

  await page.getByRole("checkbox", { name: "Legal revision" }).click()
  await page.getByLabel("Source file").setInputFiles({
    name: "constitution-amendment.pdf",
    mimeType: "application/pdf",
    buffer: onePagePdf(),
  })
  await page.getByRole("button", { name: "Start ingestion" }).click()

  await expect(
    page.getByText("Set the legal revision effective date."),
  ).toBeVisible()
  expect(requests.sourceUploadBody).toBeUndefined()
})

test("Admin uploads small R2 sources without API bearer auth on the presigned PUT", async ({
  page,
}) => {
  const requests = await mockAdminApi(page, { uploadBackend: "r2" })

  await page.goto("/admin")
  await page.getByRole("button", { name: "Upload source" }).click()

  await page.getByLabel("Instrument slug").fill(`cfrn-1999-r2-${Date.now()}`)
  await page.getByLabel("Source title").fill("R2 browser PDF source")
  await page.getByLabel("Source URL").fill("https://example.test/cfrn.pdf")
  await page.getByLabel("Source file").setInputFiles({
    name: "constitution.pdf",
    mimeType: "application/pdf",
    buffer: onePagePdf(),
  })
  await page.getByRole("button", { name: "Start ingestion" }).click()

  await expect(
    page.getByText("Source upload completed and ingestion queued."),
  ).toBeVisible()
  expect(requests.r2Puts).toBe(1)
  expect(requests.r2Authorizations).toBe(0)
  expect(requests.completeExpectedVersion).toBe(1)
})

test("Admin uploads large R2 sources through multipart part URLs", async ({
  page,
}) => {
  const requests = await mockAdminApi(page, {
    multipartRequired: true,
    uploadBackend: "r2",
  })

  await page.goto("/admin")
  await page.getByRole("button", { name: "Upload source" }).click()

  await page
    .getByLabel("Instrument slug")
    .fill(`cfrn-1999-r2-large-${Date.now()}`)
  await page.getByLabel("Source title").fill("R2 multipart PDF source")
  await page.getByLabel("Source URL").fill("https://example.test/cfrn.pdf")
  await page.getByLabel("Source file").setInputFiles({
    name: "constitution.pdf",
    mimeType: "application/pdf",
    buffer: onePagePdf(),
  })
  await page.getByRole("button", { name: "Start ingestion" }).click()

  await expect(
    page.getByText("Source upload completed and ingestion queued."),
  ).toBeVisible()
  expect(requests.multipartRequests).toBe(1)
  expect(requests.r2Puts).toBe(1)
  expect(requests.completedParts).toBe(1)
  expect(requests.completeExpectedVersion).toBe(2)
})

test("Admin reconnects streamed run events and keeps five-second polling as fallback", async ({
  page,
}) => {
  const requests = await mockAdminApi(page, { eventStream: "fail-once" })

  await page.goto("/admin")

  await expect
    .poll(() => requests.eventStream, { timeout: 5000 })
    .toBeGreaterThanOrEqual(2)
  await expect(
    page.getByText("SSE stream resumed after reconnect."),
  ).toBeVisible()
  await expect(page.getByLabel("Run event stream status")).toContainText(
    /Live events streaming|Polling every 5 seconds/,
  )

  const polledRuns = requests.runs
  await expect
    .poll(() => requests.runs, { timeout: 7000 })
    .toBeGreaterThan(polledRuns)
})

test("Admin sees provisional page previews and source-span evidence before review decisions", async ({
  page,
}) => {
  await mockAdminApi(page)

  await page.goto("/admin")
  await page.getByRole("tab", { name: "Page boundaries" }).click()

  await expect(page.getByLabel("Provisional preview page 1")).toContainText(
    "Provisional preview",
  )
  await page.getByRole("button", { name: /p\.2 Legal Body/ }).click()
  await expect(page.getByLabel("Provisional preview page 2")).toContainText(
    "Section 37",
  )
  await expect(
    page.getByText("Section 37. The privacy of citizens is hereby guaranteed."),
  ).toBeVisible()

  await page.getByRole("tab", { name: "Review queue" }).click()
  await expect(page.getByLabel("Source preview")).toContainText("native-pdf-v1")
  await page.getByRole("button", { name: /Source span page 2 box 1/ }).click()
  await expect(page.getByText("Selected source span p.2")).toBeVisible()
  await expect(page.getByText("Chapter IV")).toBeVisible()

  await page
    .getByLabel("Decision reason")
    .fill("Reviewer needs a source wording correction.")
  await page.getByRole("button", { name: "Request correction" }).click()
  await expect(page.getByText("Review decision recorded.")).toBeVisible()
})

test("Admin can confirm pages, correct review text, control runs, inspect benchmarks, and publish", async ({
  page,
}) => {
  const requests = await mockAdminApi(page)

  await page.goto("/admin")
  await expect(
    page.getByRole("button", { exact: true, name: "Resume" }),
  ).toBeEnabled()
  await expect(
    page.getByRole("button", { exact: true, name: "Retry" }),
  ).toBeDisabled()
  await expect(
    page.getByRole("button", { exact: true, name: "Cancel" }),
  ).toBeEnabled()

  await page.getByRole("button", { exact: true, name: "Resume" }).click()
  await expect(page.getByText("Run control saved.").last()).toBeVisible()
  await page.getByRole("button", { exact: true, name: "Cancel" }).click()
  await expect(page.getByText("Run control saved.").last()).toBeVisible()

  await page.getByRole("button", { name: /Native Extraction Failed/ }).click()
  await expect(
    page.getByRole("button", { exact: true, name: "Retry" }),
  ).toBeEnabled()
  await page.getByRole("button", { exact: true, name: "Retry" }).click()
  await expect(page.getByText("Run control saved.").last()).toBeVisible()

  await page.getByRole("button", { name: /Publishing Cancelled/ }).click()
  await expect(
    page.getByRole("button", { exact: true, name: "Cancel" }),
  ).toBeDisabled()
  await expect(
    page.getByRole("button", { exact: true, name: "Resume" }),
  ).toBeEnabled()

  await page.getByRole("tab", { name: "Page boundaries" }).click()
  await expect(page.getByText("p.1")).toBeVisible()
  await expect(page.getByText("p.2")).toBeVisible()
  await page.getByRole("button", { name: "Confirm suggested pages" }).click()
  await expect(page.getByText("Page boundaries saved.")).toBeVisible()

  await page.getByRole("tab", { name: "Review queue" }).click()
  await expect(
    page.getByRole("button", { name: /Right to private and family life/ }),
  ).toBeVisible()
  await page
    .getByLabel("Revised text")
    .fill("The privacy of citizens is hereby guaranteed and protected.")
  await page
    .getByLabel("Revision reason")
    .fill("Matched official source wording.")
  await page.getByRole("button", { name: "Save revision" }).click()
  await expect(page.getByText("Review revision saved.")).toBeVisible()
  await page
    .getByLabel("Decision reason")
    .fill("Checked against source coordinates.")
  await page.getByRole("button", { name: "Approve" }).click()
  await expect(page.getByText("Review decision recorded.")).toBeVisible()
  await expect(page.getByLabel("Source document verification")).toContainText(
    "Browser PDF source",
  )
  await page
    .getByLabel("Source verification reason")
    .fill("Verified source URL, hash, and page evidence.")
  await page.getByRole("button", { name: "Verify source" }).click()
  await expect(page.getByText("Source document verified.")).toBeVisible()
  expect(requests.sourceVerifications).toBe(1)
  expect(requests.sourceVerificationBody).toMatchObject({
    expected_version: 1,
    reason: "Verified source URL, hash, and page evidence.",
  })

  await page.getByRole("tab", { name: "Benchmarks" }).click()
  await expect(page.getByText("text-embedding-3-large")).toBeVisible()
  await expect(page.getByText("96%")).toBeVisible()

  await page.getByRole("tab", { name: "Corpus releases" }).click()
  await expect(page.getByText("Official 1999 Constitution PDF")).toBeVisible()
  await expect(
    page.getByText("constitution.1999.chapter4.section37"),
  ).toBeVisible()
  await expect(page.getByText("Embedding benchmark comparison")).toBeVisible()
  await expect(page.getByText("Qdrant validation")).toBeVisible()
  await expect(page.getByText("Validation passed")).toBeVisible()
  await expect(page.getByText("Actor separation")).toBeVisible()
  await expect(page.getByText("Source uploader")).toBeVisible()
  await expect(page.getByText("Publish and rollback history")).toBeVisible()
  await expect(page.getByText("Rollback completed")).toBeVisible()
  expect(requests.releaseManifests).toBeGreaterThanOrEqual(1)
  expect(requests.publicationEvidence).toBeGreaterThanOrEqual(1)
  await page.getByRole("button", { name: "Validate" }).click()
  await expect(page.getByText("Corpus release updated.").last()).toBeVisible()
  await page
    .getByLabel("Superuser override reason")
    .fill("Two-person override recorded in browser test.")
  await page.getByRole("button", { name: "Publish" }).click()
  await expect(page.getByText("Corpus release updated.").last()).toBeVisible()
})

type AdminMockOptions = {
  eventStream?: "ok" | "fail" | "fail-once"
  multipartRequired?: boolean
  uploadBackend?: "local" | "r2"
}

type AdminMockRequests = {
  completeExpectedVersion?: number
  completedParts: number
  detail: number
  eventStream: number
  multipartRequests: number
  pages: number
  publicationEvidence: number
  r2Authorizations: number
  r2Puts: number
  releaseManifests: number
  runs: number
  sourceVerificationBody?: Record<string, unknown>
  sourceVerifications: number
  sourceUploadBody?: Record<string, unknown>
}

async function mockAdminApi(
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

  await page.addInitScript(() => {
    localStorage.setItem("access_token", "playwright-admin-token")
  })
  await page.route("**/api/v1/users/me", async (route) =>
    json(route, {
      id: "99999999-9999-4999-8999-999999999999",
      email: "admin@example.test",
      full_name: "Legal Admin",
      is_active: true,
      is_superuser: true,
    }),
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
      return json(route, {
        active_runs: 1,
        blocked_runs: 0,
        failed_runs: 0,
        queue_depth: 2,
        worker_heartbeat: new Date().toISOString(),
        pages_processed: 2,
        ocr_fallback_rate: 0,
        review_issues: 1,
        auto_approval_rate: 0.25,
        embedding_progress: 0.5,
        current_production_release: "2026.09.test",
      })
    }

    if (method === "GET" && path.endsWith("/ingestion-runs")) {
      const runs = ingestionRuns()
      requests.runs += 1
      return json(route, { data: runs, count: runs.length })
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
      return json(route, { data: pages, count: pages.length })
    }

    if (method === "PATCH" && runPagesMatch) {
      const pages = sourcePages(runPagesMatch[1])
      return json(route, {
        data: pages.map((pageItem) => ({
          ...pageItem,
          inclusion_status:
            pageItem.inclusion_status === "suggested_exclude"
              ? "excluded"
              : "included",
        })),
        count: pages.length,
      })
    }

    const runDetailMatch = path.match(/\/ingestion-runs\/([^/]+)$/)
    if (method === "GET" && runDetailMatch) {
      requests.detail += 1
      return json(route, ingestionRunDetail(runDetailMatch[1]))
    }

    const retryMatch = path.match(/\/ingestion-runs\/([^/]+)\/retry$/)
    if (method === "POST" && retryMatch) {
      return json(route, {
        ...ingestionRunFor(retryMatch[1]),
        status: "queued",
      })
    }

    const cancelMatch = path.match(/\/ingestion-runs\/([^/]+)\/cancel$/)
    if (method === "POST" && cancelMatch) {
      return json(route, {
        ...ingestionRunFor(cancelMatch[1]),
        status: "cancelled",
      })
    }

    const resumeMatch = path.match(/\/ingestion-runs\/([^/]+)\/resume$/)
    if (method === "POST" && resumeMatch) {
      return json(route, {
        ...ingestionRunFor(resumeMatch[1]),
        status: "queued",
      })
    }

    if (method === "POST" && path.endsWith("/source-uploads")) {
      requests.sourceUploadBody = request.postDataJSON() as Record<
        string,
        unknown
      >
      return json(route, sourceUpload(options, requests.sourceUploadBody))
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
      return json(route, {
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
      const completeBody = request.postDataJSON() as {
        completed_parts?: unknown[]
        expected_version?: number
      }
      requests.completeExpectedVersion = completeBody.expected_version
      requests.completedParts = completeBody.completed_parts?.length ?? 0
      return json(route, {
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
      requests.sourceVerificationBody = request.postDataJSON() as Record<
        string,
        unknown
      >
      sourceVerified = true
      return json(route, sourceDocument(options, undefined, sourceVerified))
    }

    const pageSelectionMatch = path.match(
      /\/ingestion-runs\/([^/]+)\/page-selection$/,
    )
    if (method === "PATCH" && pageSelectionMatch) {
      const pages = sourcePages(pageSelectionMatch[1])
      return json(route, {
        data: pages.map((pageItem) => ({
          ...pageItem,
          inclusion_status:
            pageItem.inclusion_status === "suggested_exclude"
              ? "excluded"
              : "included",
        })),
        count: pages.length,
      })
    }

    if (method === "GET" && path.endsWith("/review-items")) {
      return json(route, { data: [reviewItem(sourceVerified)], count: 1 })
    }

    if (method === "PATCH" && path.endsWith(`/review-items/${candidateId}`)) {
      return json(route, {
        ...reviewItem(sourceVerified),
        latest_revision_text:
          "The privacy of citizens is hereby guaranteed and protected.",
        revision_number: 2,
      })
    }

    if (
      method === "POST" &&
      path.endsWith(`/review-items/${candidateId}/decision`)
    ) {
      const body = request.postDataJSON() as {
        decision?: string
        reason?: string
      }
      return json(route, {
        ...reviewItem(sourceVerified),
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
            decision: body.decision ?? "approve",
            reason: body.reason ?? "Checked against source coordinates.",
            created_at: new Date().toISOString(),
          },
        ],
      })
    }

    if (method === "GET" && path.endsWith("/corpus-releases")) {
      return json(route, { data: [corpusRelease()], count: 1 })
    }

    if (
      method === "GET" &&
      path.endsWith(`/corpus-releases/${releaseId}/manifest`)
    ) {
      requests.releaseManifests += 1
      return json(route, corpusReleaseManifest())
    }

    if (
      method === "GET" &&
      path.endsWith(`/corpus-releases/${releaseId}/publication-evidence`)
    ) {
      requests.publicationEvidence += 1
      return json(route, releasePublicationEvidence())
    }

    if (
      method === "GET" &&
      path.endsWith(`/embedding-benchmarks/${releaseId}`)
    ) {
      return json(route, {
        release_id: releaseId,
        results: [
          {
            profile_id: "88888888-8888-4888-8888-888888888888",
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
      })
    }

    if (
      method === "POST" &&
      path.endsWith(`/corpus-releases/${releaseId}/validate`)
    ) {
      return json(route, { ...corpusRelease(), status: "approved" })
    }

    if (
      method === "POST" &&
      path.endsWith(`/corpus-releases/${releaseId}/publish`)
    ) {
      return json(route, {
        release: { ...corpusRelease(), status: "production" },
        promotion_status: "succeeded",
        vector_index_status: "promoted",
      })
    }

    return route.fulfill({ status: 404, body: `No mock for ${method} ${path}` })
  })

  return requests
}

function ingestionRuns() {
  return [ingestionRun(), failedIngestionRun(), cancelledIngestionRun()]
}

function ingestionRunFor(id: string) {
  return ingestionRuns().find((run) => run.id === id) ?? ingestionRun()
}

function ingestionRun() {
  return {
    id: runId,
    source_upload_id: uploadId,
    source_document_id: sourceDocumentId,
    created_by: "99999999-9999-4999-8999-999999999999",
    status: "waiting_for_input",
    current_stage: "verifying_upload",
    pipeline_version: "legal-ingestion-v1",
    pipeline_config: { instrument_parser: "constitution" },
    expected_page_count: 2,
    total_units: 2,
    completed_units: 1,
    failed_units: 0,
    lock_version: 4,
    error_details: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    completed_at: null,
  }
}

function failedIngestionRun() {
  return {
    ...ingestionRun(),
    id: failedRunId,
    status: "failed",
    current_stage: "native_extraction",
    completed_units: 0,
    failed_units: 1,
    error_details: { message: "Native extraction worker failed." },
    lock_version: 7,
  }
}

function cancelledIngestionRun() {
  return {
    ...ingestionRun(),
    id: cancelledRunId,
    status: "cancelled",
    current_stage: "publishing",
    completed_units: 1,
    failed_units: 0,
    lock_version: 9,
  }
}

function ingestionRunDetail(id = runId) {
  const run = ingestionRunFor(id)
  return {
    ...run,
    steps: [
      {
        id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
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
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        metrics: null,
        error_details: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      {
        id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        run_id: id,
        dependency_step_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
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
        started_at: new Date().toISOString(),
        completed_at: null,
        metrics: { pages_profiled: 2 },
        error_details: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
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
        created_at: new Date().toISOString(),
      },
    ],
    tasks: [
      {
        id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        run_id: id,
        step_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
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
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
  }
}

function eventStreamBody(id: string, requestNumber: number) {
  return [
    `id: ${requestNumber}`,
    "event: ingestion_event",
    `data: ${JSON.stringify(streamedRunEvent(id, requestNumber))}`,
    "",
    "",
  ].join("\n")
}

function streamedRunEvent(id: string, requestNumber: number) {
  return {
    id: "abababab-abab-4aba-8bab-abababababab",
    run_id: id,
    step_id: null,
    sequence: requestNumber,
    event_type: "stream_reconnected",
    stage: "profiling",
    message: "SSE stream resumed after reconnect.",
    payload: { request_number: requestNumber },
    created_at: new Date().toISOString(),
  }
}

function sourcePages(id = runId) {
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
      created_at: new Date().toISOString(),
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
      created_at: new Date().toISOString(),
    },
  ]
}

function sourceDocument(
  options: AdminMockOptions = {},
  body?: Record<string, unknown>,
  verified = false,
) {
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
    retrieved_at: new Date().toISOString(),
    source_tier: "official",
    is_legal_revision: body?.is_legal_revision ?? false,
    legal_revision_effective_at: body?.legal_revision_effective_at ?? null,
    parser_version: "constitution-hierarchy-v1",
    verification_status: verified ? "verified" : "unverified",
    created_by: "99999999-9999-4999-8999-999999999999",
    verified_by: verified ? "99999999-9999-4999-8999-999999999999" : null,
    verified_at: verified ? new Date().toISOString() : null,
    lock_version: verified ? 2 : 1,
    created_at: new Date().toISOString(),
  }
}

function reviewItem(sourceVerified = false) {
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
    canonical_path: "constitution.1999.chapter4.section37",
    sort_key: "004.037",
    raw_text: "The privacy of citizens is hereby guaranteed.",
    latest_revision_text: null,
    normalized_text: "the privacy of citizens is hereby guaranteed.",
    source_page_start: 2,
    source_page_end: 2,
    source_spans: [{ page: 2, bbox: [72, 120, 520, 180] }],
    ancestor_headings: ["Chapter IV", "Fundamental Rights"],
    parser_version: "constitution-hierarchy-v1",
    extractor_version: "native-pdf-v1",
    parser_confidence: 0.81,
    extractor_confidence: 0.9,
    status: "needs_review",
    blocking_issue_count: 1,
    revision_number: 1,
    lock_version: 2,
    issues: [
      {
        id: "12121212-1212-4121-8121-121212121212",
        candidate_id: candidateId,
        issue_type: "source_span_coverage",
        severity: "blocking",
        status: "open",
        blocking: true,
        message: "Candidate requires source-span verification.",
        evidence: { page: 2 },
        created_at: new Date().toISOString(),
      },
    ],
    revisions: [],
    decisions: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
}

function corpusRelease() {
  return {
    id: releaseId,
    version: "2026.09.test",
    status: "validating",
    source_manifest_hash: "b".repeat(64),
    embedding_model: "text-embedding-3-large",
    embedding_model_version: "pinned",
    parser_version: "constitution-hierarchy-v1",
    validation_report: { unresolved_gates: [] },
    approved_by: null,
    approved_at: null,
    lock_version: 3,
    created_at: new Date().toISOString(),
    evidence_count: 1,
  }
}

function corpusReleaseManifest() {
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
      size_bytes: 512,
      artifact_metadata: {
        release_id: releaseId,
        source_manifest_hash: "b".repeat(64),
      },
      created_at: new Date().toISOString(),
    },
    manifest: {
      source_documents: [
        {
          id: sourceDocumentId,
          title: "Official 1999 Constitution PDF",
          authority: "Official Gazette",
          sha256: "a".repeat(64),
          page_count: 3,
        },
      ],
      entries: [
        {
          provision_version_id: "91919191-9191-4191-9191-919191919191",
          source_document_id: sourceDocumentId,
          canonical_path: "constitution.1999.chapter4.section37",
          source_page_start: 2,
          source_page_end: 2,
        },
      ],
    },
  }
}

function releasePublicationEvidence() {
  return {
    release_id: releaseId,
    release_version: "2026.09.test",
    vector_indexes: [
      {
        id: "92929292-9292-4292-9292-929292929292",
        release_id: releaseId,
        embedding_run_id: "93939393-9393-4393-9393-939393939393",
        profile_id: "88888888-8888-4888-8888-888888888888",
        collection_name: "law_padi_test_vector",
        alias_name: "law_padi_production",
        status: "ready",
        point_count: 1,
        vector_dimensions: 3072,
        payload_schema_hash: "d".repeat(64),
        checksum: "e".repeat(64),
        validation_report: {
          is_valid: true,
          remote_point_count: 1,
          smoke_queries: [{ passed: true, expected_point_id: "point-1" }],
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
    promotion_attempts: [
      {
        id: "94949494-9494-4494-9494-949494949494",
        release_id: releaseId,
        vector_index_id: "92929292-9292-4292-9292-929292929292",
        requested_by: "99999999-9999-4999-8999-999999999999",
        status: "rolled_back",
        previous_release_id: null,
        previous_collection_name: "law_padi_previous",
        target_collection_name: "law_padi_test_vector",
        rollback_completed: true,
        error_details: { phase: "database_promotion" },
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
      },
    ],
    actor_separation: {
      current_actor_id: "99999999-9999-4999-8999-999999999999",
      source_uploader_ids: ["99999999-9999-4999-8999-999999999999"],
      current_actor_is_source_uploader: true,
      approved_by: null,
      approved_by_differs_from_uploaders: null,
      superuser_override_recorded: true,
      override_reasons: ["Two-person override recorded in browser test."],
    },
  }
}

function sourceUpload(
  options: AdminMockOptions = {},
  body?: Record<string, unknown>,
) {
  const uploadBackend = options.uploadBackend ?? "local"
  const multipartRequired = options.multipartRequired ?? false
  const quarantineKey = `quarantine/${uploadId}/constitution.pdf`
  return {
    id: uploadId,
    idempotency_key: "upload-browser-test",
    source_document_id: null,
    instrument_slug: "constitution-1999",
    instrument_title: "Constitution of the Federal Republic of Nigeria 1999",
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
    expires_at: new Date().toISOString(),
    completed_at: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
}

async function json(route: Route, payload: unknown) {
  return route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(payload),
  })
}

function onePagePdf() {
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
