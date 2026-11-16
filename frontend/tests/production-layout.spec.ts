import { expect, test } from "@playwright/test"
import { legalInstrument } from "./fixtures/legal.ts"
import {
  mockChatShell,
  mockCurrentRelease,
  mockInstruments,
} from "./fixtures/shell.ts"

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
      await mockChatShell(page, {
        supported_languages: languages.map(([, label]) => label),
        answer_languages: languages.map(([language]) => language),
      })
      await mockCurrentRelease(page)
      await mockInstruments(page, [legalInstrument()])
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
