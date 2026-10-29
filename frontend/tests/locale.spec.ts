import { expect, type Page, test } from "@playwright/test"

const capabilities = {
  conversations_enabled: true,
  explanations_enabled: true,
  supported_languages: ["English"],
  question_max_length: 2000,
  build_revision: "test",
  prompt_version: "constitution-english-v8",
}

test.use({ storageState: { cookies: [], origins: [] } })

async function mockApi(page: Page) {
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
}

test("English is the default language", async ({ page }) => {
  await mockApi(page)
  await page.goto("/?intent=ask")
  await expect(
    page.getByRole("heading", { name: "Ask about Nigeria's laws." }),
  ).toBeVisible()
  await expect(page.locator("html")).toHaveAttribute("lang", "en")
})

test("Translated Browse does not repeat the edition warning in English", async ({
  page,
}) => {
  await mockApi(page)
  await page.route("**/api/v1/legal/instruments**", (route) =>
    route.fulfill({
      json: {
        data: [
          {
            slug: "constitution-1999",
            title: "1999 Constitution",
            short_title: "1999 Constitution",
            section_count: 320,
            edition_label: "LFN 2004",
            edition_note:
              "Historical source edition. Later amendments may differ.",
          },
        ],
        count: 1,
      },
    }),
  )
  await page.route("**/api/v1/legal/tree**", (route) =>
    route.fulfill({
      json: {
        data: [],
        count: 0,
        release_version: "published-test",
        edition_label: "LFN 2004",
      },
    }),
  )
  await page.goto("/laws")
  await page.getByRole("button", { name: "Language: English" }).click()
  await page.getByRole("menuitemradio", { name: "Yorùbá", exact: true }).click()
  await expect(page.locator("html")).toHaveAttribute("lang", "yo")
  await expect(
    page.getByText("Àwọn abala 320 tí a tẹ̀jáde", { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText("Historical source edition. Later amendments may differ."),
  ).toHaveCount(0)
  await expect(page.getByText(/Èyí ni Òfin-Ìpìlẹ̀ 1999/)).toBeVisible()
})

test("Switching to Yorùbá changes the interface and the page language", async ({
  page,
}) => {
  await mockApi(page)
  await page.goto("/?intent=ask")
  await page.getByRole("button", { name: "Language: English" }).click()
  await page.getByRole("menuitemradio", { name: "Yorùbá" }).click()

  await expect(
    page.getByRole("heading", { name: "Béèrè nípa àwọn òfin Nàìjíríà." }),
  ).toBeVisible()
  await expect(page.locator("html")).toHaveAttribute("lang", "yo")
  await expect(page.getByRole("textbox", { name: "Ìbéèrè rẹ" })).toBeVisible()
  // Edition notes come from the shared legal wording, also translated.
  await expect(
    page.getByText("Òfin-Ìpìlẹ̀ 1999 (ẹ̀dà 2004)").first(),
  ).toBeVisible()

  // The choice is saved on this browser.
  await page.reload()
  await expect(page.locator("html")).toHaveAttribute("lang", "yo")
  await expect(
    page.getByRole("heading", { name: "Béèrè nípa àwọn òfin Nàìjíríà." }),
  ).toBeVisible()
})

test("Settings offers every complete language and switches back to English", async ({
  page,
}) => {
  await mockApi(page)
  await page.goto("/settings")
  await page.getByRole("tab", { name: "Preferences" }).click()
  for (const name of ["English", "Pidgin", "Yorùbá", "Igbo", "Hausa"])
    await expect(page.getByRole("radio", { name })).toBeVisible()

  await page.getByRole("radio", { name: "Hausa" }).check()
  await expect(page.locator("html")).toHaveAttribute("lang", "ha")
  await expect(page.getByRole("tab", { name: "Zaɓuɓɓuka" })).toBeVisible()

  await page.getByRole("radio", { name: "English" }).check()
  await expect(page.locator("html")).toHaveAttribute("lang", "en")
  await expect(page.getByRole("tab", { name: "Preferences" })).toBeVisible()
})

test("Unreviewed interface languages are explicitly labelled Beta", async ({
  page,
}) => {
  await mockApi(page)
  await page.goto("/?intent=ask")
  await page.getByRole("button", { name: "Language: English" }).click()
  for (const language of ["Pidgin", "Yorùbá", "Hausa", "Igbo"]) {
    const choice = page.getByRole("menuitemradio", {
      name: language,
      exact: true,
    })
    await expect(choice).toContainText("Beta")
    await expect(choice).toHaveAttribute("aria-description", "Beta")
  }
  await expect(
    page.getByRole("menuitemradio", { name: "English", exact: true }),
  ).not.toContainText("Beta")
})
