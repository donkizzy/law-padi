import { readFile } from "node:fs/promises"
import { expect, type Page, test } from "@playwright/test"

// Synthetic published release: no real Act is approved by these UI fixtures.
const release = "synthetic-composite"
const constitution = "constitution-1999"
const acja = "acja-2015"
const police = "police-act-2020"
const paths = {
  [constitution]: `${constitution}.chapter4.section37`,
  [acja]: `${acja}.section9`,
  [police]: `${police}.section49`,
}
const laws = [
  {
    slug: constitution,
    title: "Constitution",
    short_title: "Constitution",
    edition_label: "Historical/source Constitution compilation (LFN 2004)",
    edition_note: "Later amendments aren't included yet.",
  },
  {
    slug: acja,
    title: "Administration of Criminal Justice Act 2015",
    short_title: "ACJA 2015",
    edition_label: "As enacted, 2015",
    edition_note: "As enacted, may have been amended.",
  },
  {
    slug: police,
    title: "Nigeria Police Act 2020",
    short_title: "Police Act 2020",
    edition_label: "As enacted, 2020",
    edition_note: "As enacted, may have been amended.",
  },
].map((law) => ({
  ...law,
  instrument_type: law.slug === constitution ? "constitution" : "act",
  section_count: 1,
  legal_statuses: ["historical"],
}))
function provision(slug: string, version = release) {
  const law = laws.find((item) => item.slug === slug)!
  const number = slug === acja ? "9" : slug === police ? "49" : "37"
  return {
    canonical_path: paths[slug],
    citation: `Section ${number}${slug === constitution ? "" : `, ${law.short_title}`}`,
    short_citation:
      slug === acja
        ? "ACJA s.9"
        : slug === police
          ? "Police Act s.49"
          : "Section 37",
    instrument_slug: slug,
    instrument_title: law.title,
    instrument_short_title: law.short_title,
    instrument_type: law.instrument_type,
    title: `Synthetic ${law.short_title} section`,
    heading: "Synthetic section",
    ancestor_headings: [],
    authoritative_text: `Synthetic ${law.short_title} wording for UI testing.`,
    source_document_id: "22222222-2222-4222-8222-222222222222",
    source_page_start: 9,
    source_page_end: 9,
    legal_status: "historical",
    release_version: version,
    provision_id: slug,
    provision_version_id: `${slug}-version`,
    release_id: "synthetic",
    kind: "section",
    edition_label: law.edition_label,
    source_title: `Synthetic ${law.short_title} fixture`,
    source_authority: "Synthetic test publisher",
    source_url: "https://example.test/synthetic.pdf",
    source_content_url: "/api/v1/legal/sources/synthetic/content",
    ancestors: [],
    children: [],
  }
}

test.use({ storageState: { cookies: [], origins: [] } })

async function mockLaws(page: Page) {
  const searches: Record<string, unknown>[] = []
  await page.route("**/api/v1/conversations/capabilities", (route) =>
    route.fulfill({
      json: {
        conversations_enabled: false,
        explanations_enabled: false,
        supported_languages: ["English"],
        question_max_length: 2000,
      },
    }),
  )
  await page.route("**/api/v1/legal/**", (route) => {
    const url = new URL(route.request().url())
    const version = url.searchParams.get("release_version") || release
    const data = (slug: string) => ({
      data: [provision(slug, version)],
      count: 1,
      outcome: "exact",
      retrieval_mode: "exact",
      release_version: version,
      edition_label: "Synthetic published source editions",
    })
    if (url.pathname.endsWith("/instruments"))
      return route.fulfill({
        json: {
          data: version === "retired-constitution" ? [laws[0]] : laws,
          count: version === "retired-constitution" ? 1 : 3,
          release_version: version,
        },
      })
    if (url.pathname.endsWith("/releases/current"))
      return route.fulfill({
        json: {
          available: true,
          release_version: release,
          edition_label: "Synthetic published source editions",
          legal_statuses: ["historical"],
        },
      })
    if (url.pathname.endsWith("/tree")) {
      const slug = url.searchParams.get("instrument") || constitution
      if (
        !paths[slug] ||
        (version === "retired-constitution" && slug !== constitution)
      )
        return route.fulfill({
          status: 404,
          json: { detail: "Law unavailable" },
        })
      const item = provision(slug, version)
      return route.fulfill({
        json: {
          data: [
            { ...item, id: item.canonical_path, number: "9", has_text: true },
          ],
          count: 1,
          scope: "children",
          parent: null,
          instrument_slug: slug,
          release_version: version,
          edition_label: item.edition_label,
        },
      })
    }
    if (url.pathname.endsWith("/search")) {
      const body = route.request().postDataJSON()
      searches.push(body)
      const slug = String(body.query).includes("ACJA")
        ? acja
        : body.instrument || constitution
      return route.fulfill({
        json: {
          ...data(slug),
          release_version: body.release_version || release,
        },
      })
    }
    if (url.pathname.includes("/provisions/")) {
      const path = decodeURIComponent(url.pathname.split("/provisions/")[1])
      const slug = path.split(".")[0]
      if (!paths[slug])
        return route.fulfill({ status: 404, json: { detail: "Missing" } })
      return route.fulfill({ json: data(slug) })
    }
    if (url.pathname.endsWith("/provision-history"))
      return route.fulfill({ json: { data: [], count: 0 } })
    return route.fulfill({ status: 404, json: { detail: "Missing" } })
  })
  return searches
}

test("A stored schedule table reads as a table, not a run-on paragraph", async ({
  page,
}) => {
  await mockLaws(page)
  await page.route("**/api/v1/legal/provisions/**", (route) =>
    route.fulfill({
      json: {
        data: [
          {
            ...provision(acja, release),
            authoritative_text:
              "Sections 165(2) and 183\nS/N | Sub-Sector | Threshold\n1 |  | ₦500m\n2 | Aquaculture |",
          },
        ],
        count: 1,
        outcome: "exact",
        retrieval_mode: "exact",
        release_version: release,
        edition_label: "Synthetic published source editions",
      },
    }),
  )

  await page.goto(`/laws/${acja}/${paths[acja]}?release=${release}`)

  await expect(page.getByText("Sections 165(2) and 183")).toBeVisible()
  const table = page.getByRole("table")
  await expect(
    table.getByRole("columnheader", { name: "Threshold" }),
  ).toBeVisible()
  await expect(table.getByRole("row")).toHaveCount(3)
  await expect(table.getByRole("cell", { name: "₦500m" })).toBeVisible()
  await expect(page.getByText("S/N | Sub-Sector")).toHaveCount(0)
})

for (const mobile of [false, true]) {
  test(`${mobile ? "Mobile" : "Desktop"}: switch laws, read an Act, inspect its source and save it`, async ({
    page,
    browserName,
  }) => {
    await page.setViewportSize(
      mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
    )
    await mockLaws(page)
    if (browserName === "chromium") {
      await page
        .context()
        .grantPermissions(["clipboard-read", "clipboard-write"])
    } else {
      // These engines do not expose Chromium's clipboard permission names.
      // Verify the copy payload through the same API; native clipboard access
      // remains covered by the Chromium version of this flow.
      await page.addInitScript(() => {
        let text = ""
        Object.defineProperty(navigator, "clipboard", {
          configurable: true,
          value: {
            writeText: async (value: string) => {
              text = value
            },
            readText: async () => text,
          },
        })
      })
    }
    await page.goto(`/laws/${constitution}?release=${release}`)
    const picker = page.getByRole("combobox", { name: "Law", exact: true })
    await expect(picker.locator("option")).toHaveCount(3)
    await picker.selectOption(acja)
    await expect(page).toHaveURL(
      new RegExp(`/laws/${acja}\\?release=${release}`),
    )
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Browse ACJA 2015.",
    )
    await page.getByRole("link", { name: /Section 9, ACJA/ }).click()
    const article = page.getByRole("article", { name: "Legal provision" })
    await expect(article).toContainText(provision(acja).authoritative_text)
    await expect(article).toContainText(
      "ACJA 2015: As enacted, may have been amended.",
    )
    await expect(article).not.toContainText("1999 Constitution")
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
      "href",
      new RegExp(`/laws/${acja}/${paths[acja]}\\?release=${release}`),
    )
    await article.getByRole("button", { name: "ACJA s.9", exact: true }).click()
    const panel = page.getByRole(mobile ? "dialog" : "complementary", {
      name: "Section details",
      exact: true,
    })
    await expect(panel).toContainText("What ACJA 2015 says")
    await expect(panel).toContainText("As enacted, may have been amended.")
    await panel
      .getByRole("button", { name: "Copy source", exact: true })
      .click()
    await expect
      .poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toContain(`ACJA 2015 (as enacted)`)
    await expect
      .poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toContain(`/laws/${acja}/${paths[acja]}?release=${release}`)
    await page.screenshot({
      path: `../output/playwright/statute-phase6-${mobile ? "mobile" : "desktop"}.png`,
      fullPage: true,
    })
    if (mobile)
      await panel.getByRole("button", { name: "Close", exact: true }).click()
    await article.getByRole("button", { name: "Save", exact: true }).click()
    await page.goto("/saved")
    await expect(
      page.getByRole("link", { name: "Open section" }),
    ).toHaveAttribute("href", `/laws/${acja}/${paths[acja]}?release=${release}`)
    await expect(
      page.getByText("ACJA 2015: As enacted, may have been amended."),
    ).toBeVisible()
    const downloadPromise = page.waitForEvent("download")
    await page.getByRole("button", { name: "Export saved sections" }).click()
    const download = await downloadPromise
    const exported = JSON.parse(
      await readFile((await download.path())!, "utf8"),
    )
    expect(exported.bookmarks[0]).toMatchObject({
      canonical_path: paths[acja],
      release_version: release,
    })
  })
}

test("Find uses the picked law for bare numbers and preserves explicit ACJA references", async ({
  page,
}) => {
  const searches = await mockLaws(page)
  await page.goto(`/laws/${acja}?release=${release}`)
  await page
    .getByRole("textbox", { name: "Search this law", exact: true })
    .fill("9")
  await page.getByRole("button", { name: "Search", exact: true }).click()
  await expect(
    page.getByRole("article", { name: "Legal provision" }),
  ).toContainText("Section 9, ACJA 2015")
  expect(searches.at(-1)).toMatchObject({
    query: "Section 9",
    instrument: acja,
    release_version: release,
  })

  await page.goto(`/?intent=find&release=${release}`)
  await page
    .getByRole("combobox", { name: "Law", exact: true })
    .selectOption(police)
  await page
    .getByRole("textbox", { name: "Your question", exact: true })
    .fill("49")
  await page.getByRole("button", { name: "Send question" }).click()
  await expect(
    page.getByRole("article", { name: "Legal provision" }),
  ).toContainText("Section 49, Police Act 2020")
  expect(searches.at(-1)).toMatchObject({
    query: "Section 49",
    instrument: police,
    release_version: release,
  })
  await page
    .getByRole("textbox", { name: "Your question", exact: true })
    .fill("ACJA s.9")
  await page.getByRole("button", { name: "Send question" }).click()
  await expect(
    page.getByRole("article", { name: "Legal provision" }),
  ).toContainText("Section 9, ACJA 2015")
  expect(searches.at(-1)).toMatchObject({
    query: "ACJA s.9",
    instrument: police,
  })
})

test("Old Constitution links and bookmarks work, while cross-law URLs are unavailable", async ({
  page,
}) => {
  await mockLaws(page)
  await page.goto(
    `/constitution/${paths[constitution]}?release=retired-constitution`,
  )
  await expect(
    page.getByRole("article", { name: "Constitutional provision" }),
  ).toContainText("Synthetic Constitution wording")
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    "href",
    new RegExp(`/laws/${constitution}/.*release=retired-constitution`),
  )
  await page.getByRole("button", { name: "Save", exact: true }).click()
  await page.goto("/saved")
  await expect(
    page.getByRole("link", { name: "Open section" }),
  ).toHaveAttribute(
    "href",
    `/laws/${constitution}/${paths[constitution]}?release=retired-constitution`,
  )
  await page.goto(`/constitution?release=retired-constitution`)
  await expect(
    page.getByRole("combobox", { name: "Law" }).locator("option"),
  ).toHaveCount(1)
  await page.goto(`/laws/${police}/${paths[acja]}?release=${release}`)
  await expect(
    page.getByText("The section link names a different law."),
  ).toBeVisible()
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
    "content",
    /noindex/,
  )
  await expect(page.getByRole("article")).toHaveCount(0)
  await page.goto(`/constitution/${paths[acja]}?release=${release}`)
  await expect(
    page.getByText("The section link names a different law."),
  ).toBeVisible()
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
    "content",
    /noindex/,
  )
})

test("Provision reader notices show on the section page and in its source panel", async ({
  page,
}) => {
  await mockLaws(page)
  const notice =
    "The published Act prints the same wording here as section 121, under the heading “Discretion in ex parte application”. The intended text of section 120 is not known from any available copy."
  await page.route("**/api/v1/legal/provisions/**", (route) =>
    route.fulfill({
      json: {
        data: [
          {
            ...provision(acja),
            notices: [
              {
                code: "repeats_other_provision",
                params: {
                  repeated: "121",
                  section: "120",
                  heading: "Discretion in ex parte application",
                },
                text: notice,
              },
            ],
          },
        ],
        count: 1,
        outcome: "exact",
        retrieval_mode: "exact",
        release_version: release,
        edition_label: "Synthetic published source editions",
      },
    }),
  )
  await page.goto(`/laws/${acja}/${paths[acja]}?release=${release}`)
  const article = page.getByRole("article", { name: "Legal provision" })
  await expect(article.getByRole("note")).toHaveText(notice)
  await article.getByRole("button", { name: "ACJA s.9", exact: true }).click()
  const panel = page.getByRole("complementary", {
    name: "Section details",
    exact: true,
  })
  await expect(panel.getByRole("note")).toHaveText(notice)
})
