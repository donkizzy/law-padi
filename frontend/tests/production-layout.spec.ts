import { expect, test } from "@playwright/test"

const languages = [
  ["en", "English"],
  ["pcm", "Pidgin"],
  ["yo", "Yorùbá"],
  ["ha", "Hausa"],
  ["ig", "Igbo"],
] as const

test.use({ storageState: { cookies: [], origins: [] } })

for (const width of [320, 375, 640, 768, 1280]) {
  for (const [code, name] of languages) {
    test(`${name}: composer actions remain aligned at ${width}px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 812 })
      await page.route("**/api/v1/conversations**", (route) =>
        route.fulfill({
          json: route.request().url().endsWith("/capabilities")
            ? {
                conversations_enabled: true,
                explanations_enabled: true,
                supported_languages: languages.map(([, label]) => label),
                answer_languages: languages.map(([language]) => language),
                question_max_length: 2000,
                build_revision: "qa",
                prompt_version: "qa",
              }
            : { data: [], count: 0 },
        }),
      )
      await page.route("**/api/v1/legal/releases/current", (route) =>
        route.fulfill({
          json: {
            release_version: "qa",
            edition_label:
              "Historical/source Constitution compilation (LFN 2004)",
            legal_statuses: ["historical"],
            available: true,
          },
        }),
      )
      await page.route("**/api/v1/legal/instruments**", (route) =>
        route.fulfill({
          json: {
            data: [
              {
                slug: "constitution-1999",
                title: "Constitution of the Federal Republic of Nigeria 1999",
                short_title: "1999 Constitution",
                instrument_type: "constitution",
              },
            ],
            count: 1,
          },
        }),
      )
      await page.goto("/?intent=find")
      if (code !== "en") {
        await page.getByRole("button", { name: "Language: English" }).click()
        await page.getByRole("menuitemradio", { name, exact: true }).click()
      }
      await expect(page.locator("html")).toHaveAttribute("lang", code)
      const editor = page.locator("[data-chat-composer]")
      await expect(editor).toBeVisible()
      await editor.fill("Section 37")
      const composer = editor.locator("..")
      const footer = composer.locator(":scope > div").first()
      const action = footer.getByRole("button")
      const metadata = footer.locator(":scope > div")
      await expect(action).toBeEnabled()
      const actionBox = await action.boundingBox()
      const metadataBox = await metadata.boundingBox()
      expect(actionBox).not.toBeNull()
      expect(metadataBox).not.toBeNull()
      // Translated labels must not force Send into a second left-hand row.
      expect(actionBox!.x).toBeGreaterThanOrEqual(
        metadataBox!.x + metadataBox!.width,
      )
      expect(actionBox!.width).toBeGreaterThanOrEqual(44)
      expect(actionBox!.height).toBeGreaterThanOrEqual(44)
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true)
      const counter = composer.locator("[aria-live]")
      expect(
        await counter.evaluate(
          (element) => element.scrollWidth <= element.clientWidth,
        ),
      ).toBe(true)
    })
  }
}
