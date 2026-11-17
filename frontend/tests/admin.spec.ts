import { expect, test } from "@playwright/test"
import type {
  CorpusReleaseManifestPublic,
  CorpusReleasePublic,
  CorpusReleasePublicationEvidencePublic,
  CorpusReleasePublishResponse,
  CorpusReleasesPublic,
  ReviewIssuePublic,
  ReviewItemPublic,
  ReviewItemsPublic,
} from "../src/client"
import {
  candidateId,
  corpusRelease,
  corpusReleaseManifest,
  nativeExtractorVersion,
  publicationFailureMessage,
  releaseId,
  releasePublicationEvidence,
  retrievalIndexBuildId,
  reviewItem,
  sourceDocumentId,
} from "./admin/fixtures.ts"
import {
  installDroppingRunEventStream,
  json,
  mockAdminApi,
  onePagePdf,
  runEventStreamLastEventIds,
} from "./admin/mockAdminApi.ts"

test.use({ storageState: { cookies: [], origins: [] } })

test("Issue resolution requires evidence and an explicit blocking override", async ({
  page,
}) => {
  await mockAdminApi(page)
  let submitted: Record<string, unknown> | undefined
  let resolved = false
  await page.route("**/api/v1/admin/review-items?*", (route) => {
    const item = reviewItem()
    if (resolved) {
      item.issues[0].status = "resolved"
      item.blocking_issue_count = 0
    }
    return json<ReviewItemsPublic>(route, { data: [item], count: 1 })
  })
  await page.route("**/api/v1/admin/review-issues/*", (route) => {
    submitted = route.request().postDataJSON()
    resolved = true
    return json<ReviewIssuePublic>(route, {
      ...reviewItem().issues[0],
      status: "resolved",
    })
  })
  await page.goto("/admin")
  await page.getByRole("tab", { name: "Review queue" }).click()
  await page.getByRole("button", { name: "Resolve review issue" }).click()
  const dialog = page.getByRole("dialog", {
    name: "Record review issue resolution",
  })
  const save = dialog.getByRole("button", { name: "Record resolution" })
  await dialog
    .getByLabel("Issue resolution reason")
    .fill("Checked the retained source and repaired mapping.")
  await dialog
    .getByLabel("Blocking issue override reason")
    .fill("Source comparison completed; obsolete extraction warning.")
  await expect(save).toBeDisabled()
  await dialog.getByLabel("Resolution evidence JSON").fill("[]")
  await expect(dialog.getByRole("alert")).toContainText("JSON object")
  await expect(save).toBeDisabled()
  await dialog
    .getByLabel("Resolution evidence JSON")
    .fill('{"source_page":2,"mapping_checked":true}')
  await save.click()
  await expect(dialog).not.toBeVisible()
  expect(submitted).toMatchObject({
    expected_version: 2,
    reason: "Checked the retained source and repaired mapping.",
    evidence: { source_page: 2, mapping_checked: true },
    superuser_override_reason:
      "Source comparison completed; obsolete extraction warning.",
  })
  await expect(
    page.getByRole("button", { name: "Resolve review issue" }),
  ).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: "Verify source" }),
  ).toBeVisible()
})

test("Legal reviewers cannot override blocking issues in the UI", async ({
  page,
}) => {
  await mockAdminApi(page, { isSuperuser: false, roles: ["legal_reviewer"] })
  await page.goto("/admin")
  await page.getByRole("tab", { name: "Review queue" }).click()
  await expect(
    page.getByText("Candidate requires source-span verification.").last(),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Resolve review issue" }),
  ).toHaveCount(0)
})

test("Admin legal workspace shows the metrics, operational alerts and tabs", async ({
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
  for (const metric of [
    "Active runs",
    "Blocked runs",
    "Failed runs",
    "Queue depth",
    "Worker heartbeat",
    "Pages processed",
    "OCR fallback",
    "Review issues",
    "Auto-approved",
    "Embedding",
    "Production",
  ]) {
    await expect(page.getByText(metric, { exact: true })).toBeVisible()
  }
  await expect(
    page.getByRole("heading", { name: "Operational alerts" }),
  ).toBeVisible()
  await expect(page.getByText("Terminal ingestion failure")).toBeVisible()
  await expect(page.getByText("HF TEI endpoint returned 502.")).toBeVisible()
  await expect(page.getByText(publicationFailureMessage)).toBeVisible()

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

test("Publisher composes approved Acts with the production Constitution", async ({
  page,
}) => {
  await mockAdminApi(page)
  const base = corpusRelease({
    status: "production",
    instrument_slugs: ["constitution-1999"],
    instrument_types: ["constitution"],
  })
  const act = corpusRelease({
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    version: "acja-reviewed",
    status: "approved",
    instrument_slugs: ["acja-2015"],
    instrument_types: ["act"],
    lock_version: 4,
  })
  const unapproved = corpusRelease({
    ...act,
    id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    version: "police-unreviewed",
    status: "validating",
    instrument_slugs: ["police-act-2020"],
  })
  let composed: CorpusReleasePublic | undefined
  let submitted: Record<string, unknown> | undefined
  await page.route("**/api/v1/admin/corpus-releases", (route) =>
    json<CorpusReleasesPublic>(route, {
      data: [base, act, unapproved, ...(composed ? [composed] : [])],
      count: composed ? 4 : 3,
    }),
  )
  await page.route("**/api/v1/admin/corpus-releases/compose", (route) => {
    submitted = route.request().postDataJSON()
    composed = corpusRelease({
      id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      version: String(submitted?.version),
      status: "building",
    })
    return json<CorpusReleasePublic>(route, composed)
  })
  await page.goto("/admin")
  await page.getByRole("tab", { name: "Corpus releases" }).click()
  const form = page.getByRole("form", { name: "Compose release" })
  await expect(form.getByText(`Base: ${base.version}`)).toBeVisible()
  await expect(
    form.getByText("police-unreviewed", { exact: false }),
  ).toHaveCount(0)
  await form.getByLabel("Release version").fill("laws-reviewed-test")
  await form
    .getByRole("checkbox", { name: "acja-2015 · acja-reviewed" })
    .check()
  await page.screenshot({
    path: "../output/playwright/statute-phase3-compose-release.png",
    fullPage: true,
  })
  await form
    .getByRole("button", { name: "Compose release", exact: true })
    .click()
  await expect(
    page.getByText("Release composed. Retrieval build queued."),
  ).toBeVisible()
  expect(submitted).toMatchObject({
    version: "laws-reviewed-test",
    base_release_id: base.id,
    expected_base_version: base.lock_version,
    members: [{ release_id: act.id, expected_version: 4 }],
  })
})

test("Composition waits for approved Acts and publisher access", async ({
  page,
}) => {
  await mockAdminApi(page, { roles: ["legal_reviewer"], isSuperuser: false })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/admin")
  await page.getByRole("tab", { name: "Corpus releases" }).click()
  const form = page.getByRole("form", { name: "Compose release" })
  await expect(
    form.getByText("Approve an Act release before composing."),
  ).toBeVisible()
  await expect(
    form.getByRole("button", { name: "Compose release", exact: true }),
  ).toBeDisabled()
  await expect(form.getByLabel("Release version")).toBeDisabled()
  await page.screenshot({
    path: "../output/playwright/statute-phase3-compose-mobile.png",
    fullPage: true,
  })
})

test("Review queue paginates the full total and filters completed candidates", async ({
  page,
}) => {
  await mockAdminApi(page)
  await page.route("**/api/v1/admin/review-items?**", async (route) => {
    const url = new URL(route.request().url())
    const skip = Number(url.searchParams.get("skip") ?? 0)
    const materialized = url.searchParams.get("status") === "materialized"
    const total = materialized ? 1 : 144
    const count = Math.min(100, total - skip)
    return json<ReviewItemsPublic>(route, {
      data: Array.from({ length: count }, (_, index) => ({
        ...reviewItem(true),
        id: `candidate-${skip + index}`,
        heading: `Candidate ${skip + index + 1}`,
        status: materialized ? "materialized" : "needs_review",
      })),
      count: total,
    })
  })
  await page.goto("/admin")
  await page.getByRole("tab", { name: "Review queue" }).click()
  await expect(page.getByText("1–100 of 144")).toBeVisible()
  await page.getByRole("button", { name: "Next", exact: true }).click()
  await expect(page.getByText("101–144 of 144")).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Next", exact: true }),
  ).toBeDisabled()
  await page.getByLabel("Candidate status").selectOption("materialized")
  await expect(page.getByText("1–1 of 1")).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Previous", exact: true }),
  ).toBeDisabled()
})

test("Review structure corrections include the metadata patch and preserve source references", async ({
  page,
}) => {
  await mockAdminApi(page)
  let submitted: Record<string, unknown> | undefined
  const item = reviewItem()
  await page.route(
    `**/api/v1/admin/review-items/${candidateId}`,
    async (route) => {
      if (route.request().method() === "PATCH") {
        submitted = route.request().postDataJSON()
        return json<ReviewItemPublic>(route, {
          ...item,
          ...submitted,
          lock_version: 3,
        })
      }
      return json<ReviewItemPublic>(route, item)
    },
  )
  await page.goto("/admin")
  await page.getByRole("tab", { name: "Review queue" }).click()
  await page.getByLabel("Provision number", { exact: true }).fill("141")
  await page
    .getByLabel("Provision heading", { exact: true })
    .fill("Interpretation")
  await page
    .getByLabel("Canonical path", { exact: true })
    .fill("constitution-1999.chapter4.section141")
  await page.getByLabel("Source spans JSON").fill("invalid JSON")
  await page
    .getByLabel("Revision reason", { exact: true })
    .fill("Checked against the retained source scan.")
  await expect(
    page.getByRole("button", { name: "Save revision", exact: true }),
  ).toBeDisabled()
  await page.getByLabel("Source spans JSON").fill(
    JSON.stringify([
      {
        page_number: 2,
        bbox: { x0: 72, y0: 120, x1: 520, y1: 180 },
        text: item.raw_text,
      },
    ]),
  )
  await page.getByRole("button", { name: "Save revision", exact: true }).click()
  await expect(page.getByText("Review revision saved.")).toBeVisible()
  expect(submitted).toMatchObject({
    number: "141",
    heading: "Interpretation",
    canonical_path: "constitution-1999.chapter4.section141",
    source_spans: [{ page_number: 2 }],
  })
})

test("Structure-only nodes can save metadata without inventing body text", async ({
  page,
}) => {
  await mockAdminApi(page)
  const item: ReviewItemPublic = {
    ...reviewItem(),
    kind: "part",
    number: "17",
    canonical_path: "police-act-2020.part17",
    raw_text: null,
    latest_revision_text: null,
    heading: "Miscellaneous provisions",
  }
  let submitted: Record<string, unknown> | undefined
  await page.route("**/api/v1/admin/review-items?**", async (route) =>
    json<ReviewItemsPublic>(route, { data: [item], count: 1 }),
  )
  await page.route(
    `**/api/v1/admin/review-items/${candidateId}`,
    async (route) => {
      if (route.request().method() === "PATCH")
        submitted = route.request().postDataJSON()
      return json<ReviewItemPublic>(route, { ...item, ...submitted })
    },
  )
  await page.goto("/admin")
  await page.getByRole("tab", { name: "Review queue" }).click()
  await page
    .getByLabel("Provision heading", { exact: true })
    .fill("MISCELLANEOUS PROVISIONS")
  await page
    .getByLabel("Revision reason", { exact: true })
    .fill("Checked the printed Part heading.")
  await page.getByRole("button", { name: "Save revision", exact: true }).click()
  await expect(page.getByText("Review revision saved.")).toBeVisible()
  expect(submitted).toHaveProperty("heading", "MISCELLANEOUS PROVISIONS")
  expect(submitted).not.toHaveProperty("revised_text")
})

test("A recovered provision starts a separate review and keeps the original candidate", async ({
  page,
}) => {
  await mockAdminApi(page)
  let submitted: Record<string, unknown> | undefined
  await page.route(
    `**/api/v1/admin/review-items/${candidateId}/derived-items`,
    async (route) => {
      submitted = route.request().postDataJSON()
      return json<ReviewItemPublic>(route, {
        ...reviewItem(),
        ...submitted,
        id: "recovered-candidate",
        status: "needs_review",
      })
    },
  )
  await page.goto("/admin")
  await page.getByRole("tab", { name: "Review queue" }).click()
  await page.getByRole("button", { name: "Add missing provision" }).click()
  const form = page.getByRole("dialog", { name: "Recover a missing provision" })
  await form
    .getByLabel("Canonical path", { exact: true })
    .fill("constitution-1999.schedule1")
  await form.getByLabel("Sort key", { exact: true }).fill("999")
  await form
    .getByLabel("Recovered provision text")
    .fill("Wording checked against the Schedule scan.")
  await form
    .getByLabel("Recovery reason")
    .fill("The parser merged a separate Schedule into the final section.")
  await form.getByRole("button", { name: "Save recovered provision" }).click()
  await expect(
    page.getByText("Recovered provision saved for review."),
  ).toBeVisible()
  expect(submitted).toMatchObject({
    kind: "schedule",
    canonical_path: "constitution-1999.schedule1",
    expected_version: 2,
  })
  expect(submitted).not.toHaveProperty("decision")
})

test("Historical release review displays preserved source exceptions", async ({
  page,
}) => {
  await mockAdminApi(page)
  await page.route("**/api/v1/admin/corpus-releases", async (route) =>
    json<CorpusReleasesPublic>(route, {
      data: [
        {
          ...corpusRelease(),
          validation_report: {
            corpus_legal_status: "historical",
            source_edition_review: {
              known_exceptions:
                "Printed duplicate 189; missing 168; punctuation retained.",
            },
            unresolved_gates: [],
          },
        },
      ],
      count: 1,
    }),
  )
  await page.goto("/admin")
  await page.getByRole("tab", { name: "Corpus releases" }).click()
  await expect(
    page.getByText("Historical source edition", { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText(/Source exceptions: Printed duplicate 189; missing 168/),
  ).toBeVisible()
})

test("Publish waits for validation and uses the updated release version", async ({
  page,
}) => {
  await mockAdminApi(page)
  let release: CorpusReleasePublic = corpusRelease({
    status: "building",
    lock_version: 4,
  })
  await page.route("**/api/v1/admin/corpus-releases", (route) =>
    json<CorpusReleasesPublic>(route, { data: [release], count: 1 }),
  )
  await page.route(
    `**/api/v1/admin/corpus-releases/${releaseId}/validate`,
    async (route) => {
      expect(route.request().postDataJSON().expected_version).toBe(4)
      release = { ...release, status: "approved", lock_version: 5 }
      return json<CorpusReleasePublic>(route, release)
    },
  )
  let published = false
  await page.route(
    `**/api/v1/admin/corpus-releases/${releaseId}/publish`,
    async (route) => {
      expect(route.request().postDataJSON().expected_version).toBe(5)
      published = true
      release = { ...release, status: "production", lock_version: 6 }
      return json<CorpusReleasePublishResponse>(route, {
        release,
        promotion_status: "succeeded",
      })
    },
  )
  await page.goto("/admin")
  await page.getByRole("tab", { name: "Corpus releases" }).click()
  await expect(
    page.getByRole("button", { name: "Publish", exact: true }),
  ).toBeDisabled()
  await expect(page.getByText(/Select Validate first/)).toBeVisible()
  expect(published).toBe(false)
  await page.getByRole("button", { name: "Validate", exact: true }).click()
  await expect(page.getByText(/You uploaded this source/)).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Publish", exact: true }),
  ).toBeDisabled()
  await page
    .getByLabel("Superuser override reason")
    .fill("Authorized local development publication after source review.")
  await expect(
    page.getByRole("button", { name: "Publish", exact: true }),
  ).toBeEnabled()
  await page.getByRole("button", { name: "Publish", exact: true }).click()
  await expect(
    page.getByRole("button", { name: "Publish", exact: true }),
  ).toBeDisabled()
  expect(published).toBe(true)
})

test("An approved Act-only release is labelled and cannot be published", async ({
  page,
}) => {
  await mockAdminApi(page)
  const actOnly = corpusRelease({
    version: "draft-acja-only",
    status: "approved",
    instrument_slugs: ["acja-2015"],
    instrument_types: ["act"],
  })
  let published = false
  await page.route("**/api/v1/admin/corpus-releases", (route) =>
    json<CorpusReleasesPublic>(route, { data: [actOnly], count: 1 }),
  )
  await page.route(
    `**/api/v1/admin/corpus-releases/${releaseId}/publish`,
    (route) => {
      published = true
      return json<CorpusReleasePublishResponse>(route, {
        release: actOnly,
        promotion_status: "succeeded",
      })
    },
  )
  await page.goto("/admin")
  await page.getByRole("tab", { name: "Corpus releases" }).click()

  await expect(page.getByText("Act only · for Compose release")).toBeVisible()
  await expect(
    page.getByText(/Publishing it would replace the live Constitution/),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Publish", exact: true }),
  ).toBeDisabled()
  expect(published).toBe(false)
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

test("Admin reconnects streamed run events and keeps polling as fallback", async ({
  page,
}) => {
  await installDroppingRunEventStream(page)
  const requests = await mockAdminApi(page)

  await page.goto("/admin")

  await expect(
    page.getByText("Initial streamed event before reconnect."),
  ).toBeVisible()
  await expect(
    page.getByText("SSE stream resumed after reconnect."),
  ).toBeVisible()
  await expect
    .poll(() => runEventStreamLastEventIds(page), { timeout: 5000 })
    .toContain("1")
  expect(await runEventStreamLastEventIds(page)).toEqual([null, "1"])
  await expect(page.getByLabel("Run event stream status")).toContainText(
    /Live events streaming|Live events unavailable; checking for updates/,
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
  await expect(page.getByLabel("Source preview")).toContainText(
    nativeExtractorVersion,
  )
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
  const requests = await mockAdminApi(page, {
    initialRunStage: "awaiting_page_confirmation",
  })

  await page.goto("/admin")
  await expect(
    page.getByRole("button", { exact: true, name: "Resume" }),
  ).toBeDisabled()
  await expect(
    page.getByRole("button", { exact: true, name: "Retry" }),
  ).toBeDisabled()
  await expect(
    page.getByRole("button", { exact: true, name: "Cancel" }),
  ).toBeEnabled()

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
  await expect(
    page.getByRole("button", { name: "Confirm suggested pages" }),
  ).toBeDisabled()
  await page.getByRole("tab", { name: "Ingestion runs" }).click()
  await page.getByRole("button", { name: /Awaiting Page Confirmation/ }).click()
  await expect(
    page.getByRole("button", { exact: true, name: "Resume" }),
  ).toBeDisabled()
  await page.getByRole("tab", { name: "Page boundaries" }).click()
  await expect(page.getByText("p.1")).toBeVisible()
  await expect(page.getByText("p.2")).toBeVisible()
  await page.getByRole("button", { name: /p\.2 Legal Body/ }).click()
  await page.getByRole("tab", { exact: true, name: "Exclude" }).click()
  await page
    .getByLabel("Page inclusion reason")
    .fill("Duplicate schedule page removed.")
  await page.getByRole("button", { name: "Confirm suggested pages" }).click()
  await expect(page.getByText("Page boundaries saved.")).toBeVisible()
  expect(requests.pageSelectionBody?.pages).toContainEqual(
    expect.objectContaining({
      inclusion_reason: "Duplicate schedule page removed.",
      inclusion_status: "excluded",
      page_number: 2,
    }),
  )

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
    page.getByText("constitution-1999.chapter4.section37"),
  ).toBeVisible()
  await expect(page.getByText("Embedding benchmark comparison")).toBeVisible()
  await expect(page.getByText("pgvector validation")).toBeVisible()
  await expect(
    page.getByText("Exact dense, lexical and join validation passed"),
  ).toBeVisible()
  await expect(page.getByText("Actor separation")).toBeVisible()
  await expect(page.getByText("Source uploader")).toBeVisible()
  await expect(page.getByText("Publish and rollback history")).toBeVisible()
  await expect(page.getByText("Rollback not needed")).toBeVisible()
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

test("Admin uses range selection, revision diffs, audit history, and OCR benchmarks", async ({
  page,
}) => {
  const requests = await mockAdminApi(page, {
    initialRunStage: "awaiting_page_confirmation",
  })

  await page.goto("/admin")

  await page.getByRole("tab", { name: "Page boundaries" }).click()
  await expect(page.getByLabel("Page range selection")).toBeVisible()
  await expect(page.getByLabel("Page filmstrip")).toBeVisible()
  await page.getByLabel("Range from page").fill("1")
  await page.getByLabel("Range to page").fill("2")
  await page
    .getByLabel("Range reason")
    .fill("Schedules at the end must be included.")
  await page.getByRole("button", { name: "Include range" }).click()
  await page.getByRole("button", { name: "Confirm suggested pages" }).click()
  await expect(page.getByText("Page boundaries saved.")).toBeVisible()
  expect(requests.pageSelectionBody?.pages).toContainEqual(
    expect.objectContaining({
      page_number: 1,
      inclusion_status: "included",
      inclusion_reason: "Schedules at the end must be included.",
    }),
  )

  await page.getByRole("tab", { name: "Review queue" }).click()
  await expect(page.getByText("No textual changes")).toBeVisible()
  await page
    .getByLabel("Revised text")
    .fill("The privacy of citizens is hereby guaranteed and protected.")
  await page
    .getByLabel("Revision reason")
    .fill("Matched official source wording.")
  await page.getByRole("button", { name: "Save revision" }).click()
  await expect(page.getByText("Review revision saved.")).toBeVisible()
  await expect(page.getByLabel("Revision diff")).toBeVisible()
  await expect(page.getByText("+ The privacy of citizens is")).toBeVisible()

  await page.getByRole("tab", { name: "Corpus releases" }).click()
  await expect(page.getByText("Audit history")).toBeVisible()
  await expect(page.getByText("corpus_release.publish")).toBeVisible()
  await expect(page.getByText("Browser test audit entry.")).toBeVisible()

  await page.getByRole("tab", { name: "Benchmarks" }).click()
  await expect(page.getByText("OCR benchmarks")).toBeVisible()
  await page.getByLabel("OCR benchmark dataset version").fill("ocr-gold-v1")
  await page.getByRole("button", { name: "Load dataset" }).click()
  await expect(page.getByText("google_document_ai").first()).toBeVisible()
  await expect(page.getByText("2 pages").first()).toBeVisible()
})

test("A release with no index build yet shows the pgvector build as pending", async ({
  page,
}) => {
  await mockAdminApi(page)
  await page.route(
    `**/api/v1/admin/corpus-releases/${releaseId}/publication-evidence`,
    (route) =>
      json<CorpusReleasePublicationEvidencePublic>(route, {
        ...releasePublicationEvidence(),
        retrieval_index_builds: [],
        promotion_attempts: [],
      }),
  )
  await page.goto("/admin")
  await page.getByRole("tab", { name: "Corpus releases" }).click()
  await expect(
    page.getByText("pgvector index build", { exact: true }),
  ).toBeVisible()
  await expect(page.getByText("Vector index evidence pending.")).toBeVisible()
  await expect(page.getByText("pgvector validation")).toHaveCount(0)
})

test("Promotion history names the pgvector index build a release went live on", async ({
  page,
}) => {
  await mockAdminApi(page)
  await page.goto("/admin")
  await page.getByRole("tab", { name: "Corpus releases" }).click()
  await expect(
    page.getByText(`enacted · build ${retrievalIndexBuildId}`, { exact: true }),
  ).toBeVisible()
})

test("The release manifest identifies a source by its document ID", async ({
  page,
}) => {
  await mockAdminApi(page)
  const manifest = corpusReleaseManifest()
  await page.route(
    `**/api/v1/admin/corpus-releases/${releaseId}/manifest`,
    (route) =>
      json<CorpusReleaseManifestPublic>(route, {
        ...manifest,
        manifest: {
          ...manifest.manifest,
          // A single-run manifest keys each source by `source_document_id`.
          source_documents: [
            { source_document_id: sourceDocumentId, authority: "Gazette" },
          ],
        },
      }),
  )
  await page.goto("/admin")
  await page.getByRole("tab", { name: "Corpus releases" }).click()
  await expect(page.getByText(sourceDocumentId, { exact: true })).toBeVisible()
  await expect(page.getByText("Untitled source")).toHaveCount(0)
})

test("Accounts without admin roles see read-only controls", async ({
  page,
}) => {
  await mockAdminApi(page, { roles: [], isSuperuser: false })

  await page.goto("/admin")

  await expect(
    page.getByRole("button", { name: "Upload source" }),
  ).toBeDisabled()
  await page.getByRole("tab", { name: "Review queue" }).click()
  await expect(page.getByText("lacks the legal_reviewer role")).toBeVisible()
  await expect(page.getByRole("button", { name: "Approve" })).toBeDisabled()
  await page.getByRole("tab", { name: "Corpus releases" }).click()
  await expect(page.getByText("lacks the corpus_publisher role")).toBeVisible()
  await expect(page.getByRole("button", { name: "Publish" })).toBeDisabled()
})
