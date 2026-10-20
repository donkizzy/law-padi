import { expect, type Page, test } from "@playwright/test"
import { mockSignedIn, SESSION_HINT_KEY } from "./utils/session.ts"

const user = {
  id: "99999999-9999-4999-8999-999999999999",
  full_name: "Test Reader",
  email: "reader@example.test",
  is_active: true,
  is_superuser: false,
}
const capabilities = {
  conversations_enabled: true,
  explanations_enabled: true,
  supported_languages: ["English"],
  question_max_length: 2000,
  build_revision: "test",
  prompt_version: "constitution-english-v8",
}

test.use({ storageState: { cookies: [], origins: [] } })

async function mockSettings(page: Page, signedIn = false) {
  let account = { ...user }
  const profileWrites: unknown[] = []
  const passwordWrites: unknown[] = []
  if (signedIn) await mockSignedIn(page, "mock-account")
  await page.route("**/api/v1/conversations**", (route) =>
    route.fulfill({
      json: new URL(route.request().url()).pathname.endsWith("/capabilities")
        ? capabilities
        : { data: [], count: 0 },
    }),
  )
  await page.route("**/api/v1/legal/releases/current", (route) =>
    route.fulfill({
      json: {
        release_version: "published-test",
        edition_label: "Historical/source Constitution compilation (LFN 2004)",
        legal_statuses: ["historical"],
        available: true,
      },
    }),
  )
  await page.route("**/api/v1/users/me**", (route) => {
    if (route.request().url().includes("password")) {
      passwordWrites.push(route.request().postDataJSON())
      return route.fulfill({
        json: { message: "Password updated successfully" },
      })
    }
    if (route.request().method() === "PATCH") {
      const data = route.request().postDataJSON()
      profileWrites.push(data)
      account = { ...account, ...data }
    }
    return route.fulfill({ json: account })
  })
  return { profileWrites, passwordWrites }
}

test("Guest settings shows honest identity, supported language, and a sign-in path", async ({
  page,
}) => {
  await mockSettings(page)
  await page.goto("/settings")
  await expect(page.getByRole("tabpanel", { name: "Profile" })).toContainText(
    "browsing as a guest",
  )
  await expect(page.getByText("amos@example.com")).toHaveCount(0)
  await expect(page.getByText("Email verified")).toHaveCount(0)
  await expect(
    page
      .getByRole("tabpanel", { name: "Profile" })
      .getByRole("link", { name: "Sign in" }),
  ).toBeVisible()
  await page.getByRole("tab", { name: "Preferences" }).click()
  await expect(page.getByRole("radio", { name: "English" })).toBeChecked()
  await expect(
    page.getByText(
      "Official wording of the Constitution and other laws always stays in English.",
    ),
  ).toBeVisible()
  await expect(
    page.getByRole("combobox", { name: "Default answer language" }),
  ).toHaveCount(0)
})

test("Settings tabs support arrows, selected state, and associated panels", async ({
  page,
}) => {
  await mockSettings(page)
  await page.goto("/settings")
  const profile = page.getByRole("tab", { name: "Profile", exact: true })
  await profile.focus()
  await profile.press("ArrowRight")
  await expect(page.getByRole("tab", { name: "Preferences" })).toBeFocused()
  await expect(
    page.getByRole("tabpanel", { name: "Preferences" }),
  ).toBeVisible()
})

test("Preferences persist across reload and change how the composer sends", async ({
  page,
}) => {
  await mockSettings(page)
  await page.goto("/settings")
  await page.getByRole("tab", { name: "Preferences" }).click()
  await page.getByRole("switch", { name: "Enter to send" }).click()
  await page.getByRole("button", { name: "Save changes" }).click()
  await expect(page.getByRole("status")).toContainText("Settings saved")
  await page.reload()
  await page.getByRole("tab", { name: "Preferences" }).click()
  await expect(
    page.getByRole("switch", { name: "Enter to send" }),
  ).toHaveAttribute("aria-checked", "false")
  await page.goto("/?intent=ask")
  const editor = page.getByRole("textbox", { name: "Your question" })
  await editor.fill("My question")
  await editor.press("Enter")
  await expect(editor).toHaveValue("My question\n")
  await expect(page).not.toHaveURL(/(?:[?&])c=/)
})

test("Blocked browser storage never displays a successful save", async ({
  page,
}) => {
  await mockSettings(page)
  await page.addInitScript(() => {
    Storage.prototype.setItem = () => {
      throw new Error("Storage blocked")
    }
  })
  await page.goto("/settings")
  await page.getByRole("tab", { name: "Preferences" }).click()
  await page.getByRole("switch", { name: "Enter to send" }).click()
  await page.getByRole("button", { name: "Save changes" }).click()
  await expect(page.getByRole("alert")).toContainText("couldn't save")
  await expect(page.getByText("Settings saved", { exact: true })).toHaveCount(0)
})

test("Profile updates the real account response and survives reload", async ({
  page,
}) => {
  const mock = await mockSettings(page, true)
  await page.goto("/settings")
  await page.getByRole("button", { name: "Edit", exact: true }).click()
  await page.getByLabel("Full name", { exact: true }).fill("Updated Reader")
  await page.getByRole("button", { name: "Save", exact: true }).click()
  await expect(page.getByRole("tabpanel", { name: "Profile" })).toContainText(
    "Updated Reader",
  )
  expect(mock.profileWrites).toEqual([{ full_name: "Updated Reader" }])
  await page.reload()
  await expect(page.getByRole("tabpanel", { name: "Profile" })).toContainText(
    "Updated Reader",
  )
})

test("Cancel restores the account profile without writing", async ({
  page,
}) => {
  const mock = await mockSettings(page, true)
  await page.goto("/settings")
  await page.getByRole("button", { name: "Edit", exact: true }).click()
  await page.getByLabel("Full name", { exact: true }).fill("Unsaved Reader")
  await page.getByRole("button", { name: "Cancel", exact: true }).click()
  await expect(page.getByRole("tabpanel", { name: "Profile" })).toContainText(
    "Test Reader",
  )
  expect(mock.profileWrites).toHaveLength(0)
})

test("Password control submits to the existing account API", async ({
  page,
}) => {
  const mock = await mockSettings(page, true)
  await page.goto("/settings")
  await page.getByRole("tab", { name: "Security" }).click()
  await page.getByTestId("current-password-input").fill("old-test-password")
  await page.getByTestId("new-password-input").fill("new-test-password")
  await page.getByTestId("confirm-password-input").fill("new-test-password")
  await page.getByRole("button", { name: "Update Password" }).click()
  await expect.poll(() => mock.passwordWrites.length).toBe(1)
  expect(mock.passwordWrites[0]).toMatchObject({
    current_password: "old-test-password",
    new_password: "new-test-password",
  })
})

test("Research export downloads real local bookmarks and source editions", async ({
  page,
}) => {
  await mockSettings(page)
  await page.addInitScript(() =>
    localStorage.setItem(
      "law-padi.saved-provisions.v1",
      JSON.stringify([
        {
          canonical_path: "constitution-1999.chapter4.section37",
          release_version: "published-test",
          saved_at: "2026-10-13T12:00:00Z",
        },
      ]),
    ),
  )
  await page.goto("/settings")
  await page.getByRole("tab", { name: "Security" }).click()
  const downloadPromise = page.waitForEvent("download")
  await page.getByRole("button", { name: "Export my research" }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe("constitution-ng-research.json")
  const stream = await download.createReadStream()
  const chunks: Buffer[] = []
  for await (const chunk of stream!) chunks.push(chunk)
  const data = JSON.parse(Buffer.concat(chunks).toString())
  expect(data.bookmarks[0].release_version).toBe("published-test")
  expect(data.conversations).toEqual([])
})

test("Clearing local research requires confirmation and preserves login", async ({
  page,
}) => {
  await mockSettings(page, true)
  await page.addInitScript(() => {
    localStorage.setItem("law-padi.saved-provisions.v1", "[]")
    sessionStorage.setItem("law-padi.draft.v1.new", "Unfinished question")
  })
  await page.goto("/settings")
  await page.getByRole("tab", { name: "Security" }).click()
  await page.getByRole("button", { name: "Clear bookmarks and drafts" }).click()
  await page.getByRole("button", { name: "Keep my research" }).click()
  expect(
    await page.evaluate(() => sessionStorage.getItem("law-padi.draft.v1.new")),
  ).toBe("Unfinished question")
  await page.getByRole("button", { name: "Clear bookmarks and drafts" }).click()
  await page
    .getByRole("button", { name: "Clear local research", exact: true })
    .click()
  expect(
    await page.evaluate(() => sessionStorage.getItem("law-padi.draft.v1.new")),
  ).toBeNull()
  expect(
    await page.evaluate((key) => localStorage.getItem(key), SESSION_HINT_KEY),
  ).toBe("1")
})

test("A confirmed account takes in this browser's research and guest chats", async ({
  page,
}) => {
  await mockSettings(page, true)
  // Registered later, so it wins over mockSettings' unconfirmed user.
  await page.route("**/api/v1/users/me", (route) =>
    route.fulfill({
      json: { ...user, email_verified_at: "2026-10-01T00:00:00Z" },
    }),
  )
  const merged: unknown[] = []
  const preferenceWrites: unknown[] = []
  let claims = 0
  await page.route("**/api/v1/conversations/claim", (route) => {
    claims += 1
    return route.fulfill({ json: { claimed_count: 2 } })
  })
  await page.route("**/api/v1/account/saved-provisions/merge", (route) => {
    const body = route.request().postDataJSON() as { items: unknown[] }
    merged.push(...body.items)
    return route.fulfill({
      json: [
        ...body.items,
        {
          canonical_path: "chapter-iv/section-40",
          release_version: "published-test",
          saved_at: "2026-09-01T00:00:00Z",
        },
      ],
    })
  })
  await page.route("**/api/v1/account/preferences", (route) => {
    if (route.request().method() === "PUT") {
      preferenceWrites.push(route.request().postDataJSON())
      return route.fulfill({ json: route.request().postDataJSON() })
    }
    return route.fulfill({ json: null })
  })

  await page.goto("/login")
  await page.evaluate(() =>
    localStorage.setItem(
      "law-padi.saved-provisions.v1",
      JSON.stringify([
        {
          canonical_path: "chapter-iv/section-35",
          release_version: "published-test",
          saved_at: "2026-10-01T00:00:00Z",
        },
      ]),
    ),
  )
  await page.goto("/settings")

  await expect(
    page.getByText("Your 2 chats are now in your account."),
  ).toBeVisible()
  expect(claims).toBe(1)
  expect(merged).toEqual([
    expect.objectContaining({ canonical_path: "chapter-iv/section-35" }),
  ])
  // The browser now mirrors the account, including what was saved elsewhere.
  await expect
    .poll(() =>
      page.evaluate(() =>
        JSON.parse(
          localStorage.getItem("law-padi.saved-provisions.v1") ?? "[]",
        ).map((item: { canonical_path: string }) => item.canonical_path),
      ),
    )
    .toEqual(["chapter-iv/section-35", "chapter-iv/section-40"])
  // An account with no saved preferences adopts this browser's.
  await expect
    .poll(() => preferenceWrites)
    .toEqual([
      { enter_to_send: true, follow_latest: true, open_sources: false },
    ])
  await expect(page.getByText("Confirm your email address")).toHaveCount(0)
})
