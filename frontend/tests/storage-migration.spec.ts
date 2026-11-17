import { expect, type Page, test } from "@playwright/test"
import { legalSearchResponse, legalSearchResult } from "./fixtures/legal.ts"
import {
  mockChatShell,
  mockCurrentRelease,
  mockInstruments,
} from "./fixtures/shell.ts"

// A browser that used the product under its earlier name keeps everything it
// saved: each key moves to its constitution.ng name once, and the old one goes.

test.use({ storageState: { cookies: [], origins: [] } })

const bookmark = {
  canonical_path: "constitution-1999.chapter4.section37",
  release_version: "published-test",
  saved_at: "2026-10-13T12:00:00Z",
}

async function mockApi(page: Page) {
  await mockChatShell(page)
  await mockCurrentRelease(page)
  await mockInstruments(page)
  await page.route("**/api/v1/legal/provisions/**", (route) =>
    route.fulfill({
      json: legalSearchResponse({ data: [legalSearchResult()] }),
    }),
  )
}

/** Write `entries` under the old names, then load the app as that browser. */
async function seedOldBrowser(
  page: Page,
  local: Record<string, string>,
  session: Record<string, string> = {},
) {
  // Seed once from a page of the app's origin, then reload as a returning visit.
  await page.goto("/privacy")
  await page.evaluate(
    ({ local, session }) => {
      localStorage.clear()
      sessionStorage.clear()
      for (const [key, value] of Object.entries(local))
        localStorage.setItem(key, value)
      for (const [key, value] of Object.entries(session))
        sessionStorage.setItem(key, value)
    },
    { local, session },
  )
}

const storedKeys = (page: Page) =>
  page.evaluate(() => ({
    local: Object.fromEntries(
      Object.keys(localStorage).map((key) => [key, localStorage.getItem(key)]),
    ),
    session: Object.fromEntries(
      Object.keys(sessionStorage).map((key) => [
        key,
        sessionStorage.getItem(key),
      ]),
    ),
  }))

test("Bookmarks, language, settings, theme and drafts survive the rename", async ({
  page,
}) => {
  await mockApi(page)
  const preferences = JSON.stringify({
    enterToSend: false,
    followLatest: false,
    openSources: true,
    language: "yoruba",
  })
  await seedOldBrowser(
    page,
    {
      "law-padi.saved-provisions.v2": JSON.stringify([bookmark]),
      "law-padi.saved-provisions.v2.migrated": "1",
      "law-padi.preferences.v1": preferences,
      "law-padi-theme": "dark",
    },
    { "law-padi.draft.v2.new": "Unfinished question" },
  )

  await page.goto("/saved")
  await expect(page.locator("html")).toHaveAttribute("lang", "yo")
  await expect(page.locator("html")).toHaveClass(/\bdark\b/)
  await expect(
    page.locator(`a[href*="${bookmark.canonical_path}"]`),
  ).toHaveAttribute(
    "href",
    `/laws/constitution-1999/${bookmark.canonical_path}?release=${bookmark.release_version}`,
  )

  expect(await storedKeys(page)).toEqual({
    local: {
      "constitution-ng.saved-provisions.v2": JSON.stringify([bookmark]),
      "constitution-ng.saved-provisions.v2.migrated": "1",
      "constitution-ng.preferences.v1": preferences,
      "constitution-ng.theme": "dark",
    },
    session: { "constitution-ng.draft.v2.new": "Unfinished question" },
  })

  // The draft and the Enter-to-send setting still shape the composer.
  await page.goto("/?intent=ask")
  const editor = page.locator("textarea")
  await expect(editor).toHaveValue("Unfinished question")
  // With Enter to send off, Enter adds a line instead of sending.
  await editor.press("Enter")
  await expect(editor).toHaveValue(/^\n?Unfinished question\n?$/)
  expect(await editor.inputValue()).toContain("\n")
  await expect(page).not.toHaveURL(/(?:[?&])c=/)
})

test("An account's bookmarks and sync markers move with their account suffix", async ({
  page,
}) => {
  await mockApi(page)
  const accountBookmarks = JSON.stringify([bookmark])
  await seedOldBrowser(page, {
    "law-padi.saved-provisions.v2.account-1": accountBookmarks,
    "law-padi.saved-provisions.v2.migrated": "1",
    "law-padi.synced-account": "account-1",
    "law-padi.synced-account.account-1": "1",
  })

  await page.goto("/privacy")

  const { local } = await storedKeys(page)
  expect(local).toMatchObject({
    "constitution-ng.saved-provisions.v2.account-1": accountBookmarks,
    "constitution-ng.synced-account": "account-1",
    "constitution-ng.synced-account.account-1": "1",
  })
  expect(
    Object.keys(local).filter((key) => key.startsWith("law-padi")),
  ).toEqual([])
})

test("A value already saved under the new name is kept", async ({ page }) => {
  await mockApi(page)
  const current = JSON.stringify({ language: "hausa" })
  await seedOldBrowser(page, {
    "law-padi.preferences.v1": JSON.stringify({ language: "yoruba" }),
    "constitution-ng.preferences.v1": current,
  })

  await page.goto("/privacy")

  await expect(page.locator("html")).toHaveAttribute("lang", "ha")
  const { local } = await storedKeys(page)
  expect(local["constitution-ng.preferences.v1"]).toBe(current)
  expect(local["law-padi.preferences.v1"]).toBeUndefined()
})
