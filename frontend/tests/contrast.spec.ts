import { expect, test } from "@playwright/test"
import { mockChatShell } from "./fixtures/shell.ts"
import { contrastRatio } from "./utils/contrast.ts"

test.use({ storageState: { cookies: [], origins: [] } })

// Surfaces that carry `text-muted-foreground` copy in the light theme.
const surfaces = [
  "--background",
  "--card",
  "--secondary",
  "--muted",
  "--accent",
  "--sidebar",
  "--sidebar-accent",
  "--legal-blue-soft",
  "--legal-amber-soft",
  "--legal-red-soft",
]

test("Secondary text meets WCAG AA contrast on every light surface", async ({
  page,
}) => {
  await mockChatShell(page)
  await page.goto("/")
  const tokens = await page.evaluate(
    (names) => {
      const style = getComputedStyle(document.documentElement)
      return Object.fromEntries(
        names.map((name) => [name, style.getPropertyValue(name).trim()]),
      )
    },
    ["--muted-foreground", ...surfaces],
  )

  expect(
    await page.evaluate(() =>
      document.documentElement.classList.contains("dark"),
    ),
  ).toBe(false)
  for (const surface of surfaces)
    expect(
      contrastRatio(tokens["--muted-foreground"], tokens[surface]),
      `--muted-foreground on ${surface}`,
    ).toBeGreaterThanOrEqual(4.5)
})
