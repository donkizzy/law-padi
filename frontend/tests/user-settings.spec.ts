import { expect, type Page, test } from "@playwright/test"
import type { ClaimResult, Message } from "../src/client"
import {
  preferencesPublic,
  savedProvision,
  userPublic,
} from "./fixtures/account.ts"
import { legalInstrument } from "./fixtures/legal.ts"
import {
  mockChatShell,
  mockCurrentRelease,
  mockInstruments,
} from "./fixtures/shell.ts"
import { mockSignedIn, SESSION_HINT_KEY } from "./utils/session.ts"

const user = userPublic()

test.use({ storageState: { cookies: [], origins: [] } })

async function mockSettings(page: Page, signedIn = false) {
  let account = user
  const profileWrites: unknown[] = []
  const emailRequests: unknown[] = []
  const passwordWrites: unknown[] = []
  if (signedIn) await mockSignedIn(page, "mock-account")
  await mockChatShell(page)
  await mockCurrentRelease(page)
  await mockInstruments(page)
  await page.route("**/api/v1/users/me**", (route) => {
    if (route.request().url().endsWith("/email-change")) {
      emailRequests.push(route.request().postDataJSON())
      return route.fulfill({
        json: {
          message: "Check the new email address to confirm the change.",
        } satisfies Message,
      })
    }
    if (route.request().url().includes("password")) {
      passwordWrites.push(route.request().postDataJSON())
      return route.fulfill({
        json: { message: "Password updated successfully" } satisfies Message,
      })
    }
    if (route.request().method() === "PATCH") {
      const data = route.request().postDataJSON()
      profileWrites.push(data)
      account = userPublic({ ...account, ...data })
    }
    return route.fulfill({ json: account })
  })
  return { profileWrites, passwordWrites, emailRequests }
}

test("Settings lists every published law with its own source caveat", async ({
  page,
}) => {
  await mockSettings(page)
  await mockInstruments(page, [
    legalInstrument({
      slug: "constitution-1999",
      edition_label: "LFN 2004",
      edition_note: "Constitution: later amendments are not included.",
    }),
    legalInstrument({
      slug: "acja-2015",
      title: "Administration of Criminal Justice Act 2015",
      short_title: "ACJA 2015",
      instrument_type: "act",
      section_count: 495,
      edition_label: "As enacted, 2015",
      edition_note: "ACJA: as enacted, may have been amended.",
    }),
    legalInstrument({
      slug: "police-act-2020",
      title: "Nigeria Police Act 2020",
      short_title: "Police Act 2020",
      instrument_type: "act",
      section_count: 150,
      edition_label: "As enacted, 2020",
      edition_note: "Police Act: as enacted, may have been amended.",
    }),
  ])
  await page.goto("/settings")
  for (const label of [
    "1999 Constitution (2004 edition)",
    "ACJA 2015 (as enacted)",
    "Police Act 2020 (as enacted)",
  ])
    await expect(page.getByText(label, { exact: true })).toBeVisible()
  for (const note of [
    "This is the 1999 Constitution as published in 2004. Later amendments aren't included yet, so a section may have changed since.",
    "ACJA 2015: As enacted, may have been amended.",
    "Police Act 2020: As enacted, may have been amended.",
  ])
    await expect(page.getByText(note, { exact: true })).toBeVisible()
})

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

test("An email change requires the password and keeps the current address until confirmed", async ({
  page,
}) => {
  const mock = await mockSettings(page, true)
  await page.goto("/settings")
  await page.getByRole("button", { name: "Edit", exact: true }).click()
  await page.getByLabel("Email", { exact: true }).fill("new@example.test")
  await page.getByRole("button", { name: "Save", exact: true }).click()
  await expect(page.getByText("Enter your current password.")).toBeVisible()
  expect(mock.emailRequests).toHaveLength(0)
  await page
    .getByLabel("Current Password", { exact: true })
    .fill("test-password")
  await page.getByRole("button", { name: "Save", exact: true }).click()
  await expect(
    page.getByText("Check the new email address to confirm the change."),
  ).toBeVisible()
  await expect(page.getByRole("tabpanel", { name: "Profile" })).toContainText(
    user.email,
  )
  expect(mock.profileWrites).toHaveLength(0)
  expect(mock.emailRequests).toEqual([
    { email: "new@example.test", current_password: "test-password" },
  ])
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

test("Opening an email confirmation link waits for the reader to confirm", async ({
  page,
}) => {
  let requests = 0
  await page.route("**/api/v1/users/verify-email", (route) => {
    requests += 1
    return route.fulfill({
      json: { message: "Email confirmed" } satisfies Message,
    })
  })
  await page.goto("/verify-email?token=dummy-email-change-token")
  const confirm = page.getByRole("button", { name: "Confirm email address" })
  await expect(confirm).toBeVisible()
  expect(requests).toBe(0)
  await confirm.click()
  await expect(
    page.getByRole("heading", { name: "Email confirmed" }),
  ).toBeVisible()
  expect(requests).toBe(1)
})

test("Research export downloads real local bookmarks and source editions", async ({
  page,
}) => {
  await mockSettings(page)
  await page.addInitScript(() =>
    localStorage.setItem(
      "constitution-ng.saved-provisions.v2",
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
    localStorage.setItem("constitution-ng.saved-provisions.v2", "[]")
    sessionStorage.setItem(
      "constitution-ng.draft.v2.signed-in.new",
      "Unfinished question",
    )
  })
  await page.goto("/settings")
  await page.getByRole("tab", { name: "Security" }).click()
  await page.getByRole("button", { name: "Clear bookmarks and drafts" }).click()
  await page.getByRole("button", { name: "Keep my research" }).click()
  expect(
    await page.evaluate(() =>
      sessionStorage.getItem("constitution-ng.draft.v2.signed-in.new"),
    ),
  ).toBe("Unfinished question")
  await page.getByRole("button", { name: "Clear bookmarks and drafts" }).click()
  await page
    .getByRole("button", { name: "Clear local research", exact: true })
    .click()
  expect(
    await page.evaluate(() =>
      sessionStorage.getItem("constitution-ng.draft.v2.signed-in.new"),
    ),
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
      json: userPublic({ email_verified_at: "2026-10-01T00:00:00Z" }),
    }),
  )
  const merged: unknown[] = []
  const preferenceWrites: unknown[] = []
  let claims = 0
  await page.route("**/api/v1/conversations/claim", (route) => {
    claims += 1
    return route.fulfill({ json: { claimed_count: 2 } satisfies ClaimResult })
  })
  await page.route("**/api/v1/account/saved-provisions/merge", (route) => {
    const body = route.request().postDataJSON() as { items: unknown[] }
    merged.push(...body.items)
    return route.fulfill({
      json: [
        ...body.items,
        savedProvision({
          canonical_path: "chapter-iv/section-40",
          saved_at: "2026-09-01T00:00:00Z",
        }),
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

  await page.addInitScript(() =>
    localStorage.setItem(
      "constitution-ng.saved-provisions.v2",
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
          localStorage.getItem(
            "constitution-ng.saved-provisions.v2.signed-in",
          ) ?? "[]",
        ).map((item: { canonical_path: string }) => item.canonical_path),
      ),
    )
    .toEqual(["chapter-iv/section-35", "chapter-iv/section-40"])
  // An account with no saved preferences adopts this browser's.
  await expect
    .poll(() => preferenceWrites)
    .toEqual([
      {
        enter_to_send: true,
        follow_latest: true,
        open_sources: false,
        language: "english",
      },
    ])
  await expect(page.getByText("Confirm your email address")).toHaveCount(0)
})

test("A different account does not import the legacy account bookmark mirror", async ({
  page,
}) => {
  await mockSettings(page, true)
  await page.addInitScript(() => {
    localStorage.setItem("law-padi.synced-account", "previous-owner")
    localStorage.setItem(
      "law-padi.saved-provisions.v1",
      JSON.stringify([
        {
          canonical_path: "private-bookmark",
          release_version: "published-test",
          saved_at: "2026-10-01T00:00:00Z",
        },
      ]),
    )
  })
  await page.route("**/api/v1/users/me", (route) =>
    route.fulfill({
      json: userPublic({ email_verified_at: "2026-10-01T00:00:00Z" }),
    }),
  )
  await page.route("**/api/v1/account/preferences", (route) =>
    route.fulfill({ json: preferencesPublic({ language: "english" }) }),
  )
  await page.route("**/api/v1/account/saved-provisions/merge", (route) =>
    route.fulfill({ json: [] }),
  )
  const merge = page.waitForRequest("**/api/v1/account/saved-provisions/merge")
  await page.goto("/settings")
  expect((await merge).postDataJSON()).toEqual({ items: [] })
})

test("A confirmed account brings its saved language to a new browser", async ({
  page,
}) => {
  await mockSettings(page, true)
  await page.route("**/api/v1/users/me", (route) =>
    route.fulfill({
      json: userPublic({ email_verified_at: "2026-10-01T00:00:00Z" }),
    }),
  )
  await page.route("**/api/v1/conversations/claim", (route) =>
    route.fulfill({ json: { claimed_count: 0 } satisfies ClaimResult }),
  )
  await page.route("**/api/v1/account/saved-provisions/merge", (route) =>
    route.fulfill({ json: [] }),
  )
  const preferenceWrites: unknown[] = []
  await page.route("**/api/v1/account/preferences", (route) => {
    if (route.request().method() === "PUT") {
      preferenceWrites.push(route.request().postDataJSON())
      return route.fulfill({ json: route.request().postDataJSON() })
    }
    return route.fulfill({ json: preferencesPublic({ language: "hausa" }) })
  })

  await page.goto("/settings")
  await expect(page.locator("html")).toHaveAttribute("lang", "ha")
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          JSON.parse(
            localStorage.getItem("constitution-ng.preferences.v1") ?? "{}",
          ).language,
      ),
    )
    .toBe("hausa")
  // The account already has a language, so nothing is written back.
  expect(preferenceWrites).toEqual([])
})

test("Deleting an account asks for the current password", async ({ page }) => {
  await mockSettings(page, true)
  const deletions: unknown[] = []
  await page.route("**/api/v1/users/me", (route) => {
    if (route.request().method() === "DELETE") {
      deletions.push(route.request().postDataJSON())
      return route.fulfill({
        json: { message: "User deleted successfully" } satisfies Message,
      })
    }
    return route.fulfill({ json: user })
  })
  await page.goto("/settings")
  await page.getByRole("tab", { name: "Security" }).click()
  await page.getByRole("button", { name: "Delete my account" }).click()

  const dialog = page.getByRole("dialog")
  const confirm = dialog.getByRole("button", { name: "Delete my account" })
  await expect(confirm).toBeDisabled()
  await dialog.getByLabel("Current Password").fill("account-password")
  await confirm.click()
  await expect
    .poll(() => deletions)
    .toEqual([{ current_password: "account-password" }])
})
