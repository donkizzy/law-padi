import { expect, type Page, test } from "@playwright/test"
import { AxiosError, type AxiosResponse } from "axios"
import { shouldRetry } from "../src/lib/query-client.ts"
import {
  currentRelease,
  legalInstrument,
  legalInstruments,
  legalSearchResponse,
  legalSearchResult,
} from "./fixtures/legal.ts"
import { mockChatShell } from "./fixtures/shell.ts"

test.use({ storageState: { cookies: [], origins: [] } })

const release = "published-policy-test"
const result = legalSearchResult({
  canonical_path: "constitution-1999.chapter4.section37",
  citation: "Section 37",
  release_version: release,
})

type Counts = { search: number; provision: number }

// Serves a search result and its provision, counting how often each is read.
async function mockCountedCorpus(page: Page): Promise<Counts> {
  const counts: Counts = { search: 0, provision: 0 }
  await mockChatShell(page, {
    conversations_enabled: false,
    explanations_enabled: false,
  })
  await page.route("**/api/v1/legal/**", (route) => {
    const { pathname } = new URL(route.request().url())
    if (pathname.endsWith("/releases/current"))
      return route.fulfill({
        json: currentRelease({ release_version: release }),
      })
    if (pathname.endsWith("/instruments"))
      return route.fulfill({
        json: legalInstruments([legalInstrument()], release),
      })
    if (pathname.endsWith("/search")) {
      counts.search += 1
      return route.fulfill({
        json: legalSearchResponse({
          data: [result],
          outcome: "exact",
          release_version: release,
        }),
      })
    }
    if (pathname.includes("/provisions/") && !pathname.endsWith("/tree")) {
      counts.provision += 1
      return route.fulfill({
        json: legalSearchResponse({
          data: [result],
          outcome: "exact",
          release_version: release,
        }),
      })
    }
    return route.fulfill({ status: 404, json: { detail: "Not found" } })
  })
  return counts
}

async function search(page: Page, query: string) {
  await page.getByRole("textbox", { name: "Your question" }).fill(query)
  await page.getByRole("button", { name: "Send question" }).click()
  await expect(
    page.getByRole("heading", { name: "Section 37", exact: true }),
  ).toBeVisible()
}

test("Returning to the tab does not repeat a search", async ({ page }) => {
  const counts = await mockCountedCorpus(page)
  await page.goto("/?intent=find")
  await search(page, "Section 37")
  expect(counts.search).toBe(1)
  await expect.poll(() => counts.provision).toBeGreaterThanOrEqual(1)
  const provisionReads = counts.provision

  // The browser reports the tab as visible again after the reader switched away.
  await page.evaluate(() => window.dispatchEvent(new Event("visibilitychange")))
  await page.waitForTimeout(500)

  expect(counts.search).toBe(1)
  expect(counts.provision).toBe(provisionReads)
})

test("Text from a named release is reused after the stale window passes", async ({
  page,
}) => {
  await page.clock.install()
  const counts = await mockCountedCorpus(page)
  await page.goto("/?intent=find")
  await search(page, "Section 37")
  await expect.poll(() => counts.provision).toBeGreaterThanOrEqual(1)
  const { search: searches, provision: provisionReads } = counts

  // Leave the results and come back after longer than the default stale time
  // but shorter than the cache lifetime of an unused query.
  await page.goBack()
  await expect(
    page.getByRole("textbox", { name: "Your question" }),
  ).toBeVisible()
  await page.clock.fastForward("02:00")
  await page.goForward()
  await expect(
    page.getByRole("heading", { name: "Section 37", exact: true }),
  ).toBeVisible()
  await page.waitForTimeout(300)

  expect(counts.search).toBe(searches)
  expect(counts.provision).toBe(provisionReads)
})

test("Retries once for network and server faults but never for client errors", () => {
  const failure = (status?: number) =>
    new AxiosError(
      "failed",
      undefined,
      undefined,
      undefined,
      status ? ({ status } as AxiosResponse) : undefined,
    )
  expect(shouldRetry(0, failure())).toBe(true)
  expect(shouldRetry(0, failure(503))).toBe(true)
  expect(shouldRetry(1, failure(503))).toBe(false)
  for (const status of [400, 401, 403, 404, 429])
    expect(shouldRetry(0, failure(status))).toBe(false)
  expect(shouldRetry(0, new Error("render failed"))).toBe(true)
})
