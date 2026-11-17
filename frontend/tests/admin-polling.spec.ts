import { expect, type Page, test } from "@playwright/test"
import type { AdminMetrics } from "../src/client"
import { adminMetrics } from "./admin/fixtures.ts"
import { json, mockAdminApi } from "./admin/mockAdminApi.ts"

test.use({ storageState: { cookies: [], origins: [] } })

/** Counts the admin API reads the page makes, by the last segment of the path. */
function watchReads(page: Page) {
  const paths: string[] = []
  page.on("request", (request) => {
    const { pathname } = new URL(request.url())
    if (request.method() === "GET" && pathname.startsWith("/api/v1/admin/"))
      paths.push(pathname)
  })
  return (suffix: string) =>
    paths.filter((path) => path.endsWith(suffix)).length
}

/** Lets a test hide and show the tab, which Playwright cannot do itself. */
async function controlVisibility(page: Page) {
  await page.addInitScript(() => {
    let hidden = false
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => (hidden ? "hidden" : "visible"),
    })
    Object.defineProperty(document, "hidden", {
      configurable: true,
      get: () => hidden,
    })
    ;(
      window as unknown as { __setHidden: (value: boolean) => void }
    ).__setHidden = (value) => {
      hidden = value
      document.dispatchEvent(new Event("visibilitychange", { bubbles: true }))
    }
  })
  return (hidden: boolean) =>
    page.evaluate(
      (value) =>
        (
          window as unknown as { __setHidden: (value: boolean) => void }
        ).__setHidden(value),
      hidden,
    )
}

const idleMetrics: AdminMetrics = {
  ...adminMetrics(),
  active_runs: 0,
  queue_depth: 0,
  worker_heartbeat: null,
}

test("An idle admin screen follows only the metrics, and slows down while they are unchanged", async ({
  page,
}) => {
  await page.clock.install()
  // Without a stream there are no events to refresh the run list.
  const requests = await mockAdminApi(page, { eventStream: "fail" })
  await page.route("**/api/v1/admin/metrics", (route) =>
    json<AdminMetrics>(route, idleMetrics),
  )
  const reads = watchReads(page)

  await page.goto("/admin")
  await expect(page.getByText("2026.09.test")).toBeVisible()
  await expect.poll(() => reads("/metrics")).toBe(1)
  await page.waitForTimeout(200)

  await page.clock.fastForward(5_100)
  await expect.poll(() => reads("/metrics")).toBe(2)
  // The first unchanged answer doubles the wait, so five more seconds is early.
  await page.clock.fastForward(5_100)
  await page.waitForTimeout(300)
  expect(reads("/metrics")).toBe(2)
  await page.clock.fastForward(5_000)
  await expect.poll(() => reads("/metrics")).toBe(3)

  await page.clock.fastForward(60_000)
  await page.waitForTimeout(300)
  expect(requests.runs).toBe(1)
  expect(reads("/my-roles")).toBe(1)
})

test("Active work is followed while the tab is shown and not while it is hidden", async ({
  page,
}) => {
  await page.clock.install()
  const setHidden = await controlVisibility(page)
  const requests = await mockAdminApi(page, { eventStream: "fail" })
  const reads = watchReads(page)

  await page.goto("/admin")
  // The metrics are what tell the screen there is work to follow.
  await expect(page.getByText("2026.09.test")).toBeVisible()
  await expect.poll(() => requests.runs).toBe(1)
  await page.waitForTimeout(200)

  await page.clock.fastForward(5_100)
  await expect.poll(() => requests.runs).toBe(2)

  await setHidden(true)
  const runs = requests.runs
  const metrics = reads("/metrics")
  await page.clock.fastForward(120_000)
  await page.waitForTimeout(300)
  expect(requests.runs).toBe(runs)
  expect(reads("/metrics")).toBe(metrics)

  // Coming back refreshes what went stale while away.
  await setHidden(false)
  await expect.poll(() => requests.runs).toBeGreaterThan(runs)
  await expect.poll(() => reads("/metrics")).toBeGreaterThan(metrics)
})

test("Each tab reads only its own data", async ({ page }) => {
  const requests = await mockAdminApi(page)
  const reads = watchReads(page)

  await page.goto("/admin")
  await expect(page.getByLabel("Run event stream status")).toBeVisible()
  // Let the stream's events (which arrive about once a second) come through.
  await expect.poll(() => requests.eventStream).toBeGreaterThanOrEqual(1)
  await page.waitForTimeout(1_500)

  expect(requests.pages).toBe(0)
  expect(reads("/review-items")).toBe(0)
  expect(reads("/corpus-releases")).toBe(0)
  expect(requests.releaseManifests).toBe(0)
  expect(requests.publicationEvidence).toBe(0)
  expect(reads("/my-roles")).toBe(1)

  await page.getByRole("tab", { name: "Review queue" }).click()
  await expect.poll(() => reads("/review-items")).toBeGreaterThanOrEqual(1)
  expect(reads("/corpus-releases")).toBe(0)

  await page.getByRole("tab", { name: "Corpus releases" }).click()
  await expect.poll(() => reads("/corpus-releases")).toBeGreaterThanOrEqual(1)
  await expect.poll(() => requests.releaseManifests).toBeGreaterThanOrEqual(1)
})

test("A run control action refreshes the run, not the review queue or releases", async ({
  page,
}) => {
  const requests = await mockAdminApi(page, {
    initialRunStage: "awaiting_page_confirmation",
  })
  const reads = watchReads(page)

  await page.goto("/admin")
  await page.getByRole("tab", { name: "Review queue" }).click()
  await expect.poll(() => reads("/review-items")).toBeGreaterThanOrEqual(1)
  await page.getByRole("tab", { name: "Ingestion runs" }).click()
  await expect(
    page.getByRole("button", { exact: true, name: "Cancel" }),
  ).toBeEnabled()
  await page.waitForTimeout(1_500)
  const reviews = reads("/review-items")
  const runs = requests.runs

  await page.getByRole("button", { exact: true, name: "Cancel" }).click()
  await expect(page.getByText("Run control saved.").last()).toBeVisible()
  await expect.poll(() => requests.runs).toBeGreaterThan(runs)
  await page.waitForTimeout(500)

  expect(reads("/review-items")).toBe(reviews)
  expect(reads("/corpus-releases")).toBe(0)
})
