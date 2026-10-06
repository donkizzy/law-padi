import { expect, type Page, test } from "@playwright/test"

const release = "published-historical-test"
const path = "constitution-1999.chapter4.section33.subsection2.paragrapha"
const edition = "Historical/source Constitution compilation (LFN 2004)"
const reference = (
  canonical_path: string,
  kind: string,
  citation: string,
  has_text = true,
) => ({
  id: canonical_path,
  canonical_path,
  kind,
  number: citation,
  heading: citation,
  citation,
  has_text,
  authoritative_text: has_text ? "Parent context retained separately." : null,
})
const provision = {
  canonical_path: path,
  citation: "Section 33(2)(a)",
  heading: "Defence from unlawful violence",
  ancestor_headings: ["Fundamental Rights"],
  authoritative_text:
    "(a) for the defence of any person from unlawful violence or for the defence of property;",
  source_document_id: "22222222-2222-4222-8222-222222222222",
  source_page_start: 34,
  source_page_end: 34,
  legal_status: "historical",
  release_version: release,
  dense_rank: null,
  lexical_rank: null,
  hybrid_score: 1,
  provision_id: "33333333-3333-4333-8333-333333333333",
  provision_version_id: "44444444-4444-4444-8444-444444444444",
  release_id: "55555555-5555-4555-8555-555555555555",
  kind: "paragraph",
  edition_label: edition,
  source_title: "Constitution compilation",
  source_authority: "Retained source authority",
  source_url: "https://example.test/constitution.pdf",
  source_content_url: `/api/v1/legal/sources/22222222-2222-4222-8222-222222222222/content?release_version=${release}`,
  ancestors: [
    reference("constitution-1999.chapter4", "chapter", "Chapter 4", false),
    reference("constitution-1999.chapter4.section33", "section", "Section 33"),
    reference(
      "constitution-1999.chapter4.section33.subsection2",
      "subsection",
      "Section 33(2)",
    ),
  ],
  children: [],
}
const response = (
  outcome = "exact",
  data = [provision],
  message: string | null = null,
) => ({
  data,
  count: data.length,
  outcome,
  retrieval_mode: "exact",
  release_version: release,
  edition_label: edition,
  message,
})

test.use({ storageState: { cookies: [], origins: [] } })

async function mockCorpus(page: Page) {
  await page.route("**/api/v1/legal/**", async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith("/releases/current"))
      return route.fulfill({
        json: {
          release_id: provision.release_id,
          release_version: release,
          index_kind: "enacted",
          embedding_run_id: provision.provision_id,
          retrieval_index_build_id: provision.provision_version_id,
          edition_label: edition,
          available: true,
          legal_statuses: ["historical"],
        },
      })
    if (url.pathname.endsWith("/provision-history"))
      return route.fulfill({
        json: response(
          "exact",
          [provision],
          "No additional published versions are stored.",
        ),
      })
    if (url.pathname.endsWith("/provisions/tree"))
      return route.fulfill({
        json: {
          data: url.searchParams.has("parent_path")
            ? [reference(path, "paragraph", provision.citation)]
            : [
                reference(
                  "constitution-1999.chapter4",
                  "chapter",
                  "Chapter 4",
                  false,
                ),
              ],
          count: 1,
          release_version: release,
          edition_label: edition,
        },
      })
    if (url.pathname.endsWith("/search")) {
      const { query, mode } = route.request().postDataJSON()
      if (query === "Section 168")
        return route.fulfill({
          json: response(
            "not_found",
            [],
            "This reference is not present in the published source edition.",
          ),
        })
      if (query === "Section 189")
        return route.fulfill({
          json: response(
            "ambiguous",
            [
              provision,
              {
                ...provision,
                canonical_path: "constitution-1999.chapter6.part2.section189",
                provision_version_id: "other-identity",
                citation: "Section 189",
                heading: "Second printed identity",
                source_page_start: 88,
              },
            ],
            "Choose by chapter, part, and page.",
          ),
        })
      if (query === "Section 33(2)(a)(i)")
        return route.fulfill({
          json: response(
            "unsupported_reference",
            [],
            "Use one section, subsection, or paragraph reference.",
          ),
        })
      return route.fulfill({
        json: response(
          query.includes("33") && mode !== "semantic" ? "exact" : "matches",
        ),
      })
    }
    if (url.pathname.includes("/provisions/"))
      return route.fulfill({ json: response() })
    if (url.pathname.includes("/sources/"))
      return route.fulfill({
        contentType: "application/pdf",
        body: "%PDF-1.4\n%%EOF",
      })
    return route.fulfill({ status: 404, json: { detail: "Not found" } })
  })
}

async function submit(page: Page, query: string) {
  await page
    .getByRole("textbox", { name: "Your constitutional question" })
    .fill(query)
  await page.getByRole("button", { name: "Send question" }).click()
}

for (const mobile of [false, true]) {
  test(`${mobile ? "Mobile" : "Desktop"}: exact lookup, source, copy, share, save, and reload`, async ({
    page,
    context,
  }) => {
    await page.setViewportSize(
      mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
    )
    await context.grantPermissions(["clipboard-read", "clipboard-write"])
    await mockCorpus(page)
    await page.goto("/")
    await expect(
      page.getByRole("article", { name: "Constitutional provision" }),
    ).toHaveCount(0)
    await expect(
      page.getByRole("combobox", { name: "Answer language" }),
    ).toHaveCount(0)
    await submit(page, "Section 33(2)(a)")
    const article = page.getByRole("article", {
      name: "Constitutional provision",
    })
    await expect(article).toContainText(provision.authoritative_text)
    await expect(article).toContainText("Historical source edition")
    await expect(
      page.getByRole("link", { name: "Chapter 4", exact: true }),
    ).toHaveCount(0)
    await page.getByRole("button", { name: "Copy wording" }).click()
    await expect
      .poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toContain(provision.authoritative_text)
    await page.getByRole("button", { name: "Share provision" }).click()
    await expect
      .poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toContain(`?release=${release}`)
    await page
      .getByRole("button", { name: "Save provision", exact: true })
      .click()
    await expect(
      page.getByRole("button", { name: "Unsave provision" }),
    ).toHaveAttribute("aria-pressed", "true")
    await page.getByRole("button", { name: "Show official source" }).click()
    const panel = mobile
      ? page.getByRole("dialog", { name: "Legal source inspector" })
      : page.getByRole("complementary", { name: "Legal source inspector" })
    await expect(panel).toContainText("PDF page 34")
    await expect(
      panel.getByRole("link", { name: "View source document" }),
    ).toHaveAttribute(
      "href",
      /release_version=published-historical-test#page=34/,
    )
    await page.keyboard.press("Escape")
    await expect(panel).not.toBeVisible()
    if (mobile)
      await expect(
        page.getByRole("button", { name: "Show official source" }),
      ).toBeFocused()
    await page
      .getByRole("button", { name: "View stored version history" })
      .click()
    await expect(
      page.getByText("No additional published versions are stored."),
    ).toBeVisible()
    await page.reload()
    await expect(
      page.getByRole("button", { name: "Unsave provision" }),
    ).toBeVisible()
    await page.goto("/saved")
    await page.getByRole("link", { name: "Open provision" }).click()
    await expect(page).toHaveURL(
      new RegExp(`/constitution/.*release=${release}`),
    )
    await expect(page.getByRole("article")).toContainText(
      provision.authoritative_text,
    )
  })
}

test("Topic queries show ranked choices before wording", async ({ page }) => {
  await mockCorpus(page)
  await page.goto("/")
  await submit(page, "privacy")
  await expect(
    page.getByRole("heading", { name: "Possible source matches" }),
  ).toBeVisible()
  await expect(
    page.getByRole("article", { name: "Constitutional provision" }),
  ).toHaveCount(0)
  await page
    .getByRole("button", { name: /Section 33\(2\)\(a\).*Defence/ })
    .click()
  await expect(page.getByRole("article")).toContainText(
    provision.authoritative_text,
  )
  await page.getByRole("button", { name: "Find related provisions" }).click()
  await expect(
    page.getByRole("heading", { name: "Possible source matches" }),
  ).toBeVisible()
  await expect(page.getByRole("article")).toHaveCount(0)
})

test("Missing, ambiguous, and unsupported references have distinct states", async ({
  page,
}) => {
  await mockCorpus(page)
  await page.goto("/")
  await submit(page, "Section 168")
  await expect(
    page.getByRole("heading", { name: "No matching provision found" }),
  ).toBeVisible()
  await submit(page, "Section 189")
  await expect(
    page.getByRole("heading", { name: "Choose the source identity" }),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: /Second printed identity.*PDF page 88/ }),
  ).toBeVisible()
  await submit(page, "Section 33(2)(a)(i)")
  await expect(
    page.getByRole("heading", { name: "Reference not supported" }),
  ).toBeVisible()
})

test("Unavailable search can retry and keyword fallback is disclosed", async ({
  page,
}) => {
  await mockCorpus(page)
  let requests = 0
  await page.route("**/api/v1/legal/search", (route) => {
    requests += 1
    return requests === 1
      ? route.fulfill({ status: 503, json: { detail: "Unavailable" } })
      : route.fulfill({
          json: {
            ...response("matches"),
            retrieval_mode: "lexical",
            message:
              "Semantic search is temporarily unavailable. Showing keyword matches.",
          },
        })
  })
  await page.goto("/")
  await submit(page, "privacy")
  await expect(
    page.getByRole("heading", { name: "Search unavailable" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "Try again" }).click()
  await expect(page.getByText(/Showing keyword matches/)).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "Possible source matches" }),
  ).toBeVisible()
})

test("Obsolete responses cannot replace a newer search; New clears results", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await mockCorpus(page)
  let finish: (() => void) | undefined
  await page.route("**/api/v1/legal/search", async (route) => {
    const { query } = route.request().postDataJSON()
    if (query === "slow") {
      await new Promise<void>((resolve) => {
        finish = resolve
      })
      await route
        .fulfill({
          json: response("matches", [
            { ...provision, heading: "Obsolete answer" },
          ]),
        })
        .catch(() => {})
      return
    }
    return route.fulfill({ json: response() })
  })
  await page.goto("/?q=slow")
  await expect(page.getByText("Searching the published source…")).toBeVisible()
  await submit(page, "Section 33(2)(a)")
  await expect(page.getByRole("article")).toBeVisible()
  finish?.()
  await expect(page.getByText("Obsolete answer")).toHaveCount(0)
  await page.getByRole("link", { name: "New search" }).click()
  await expect(page.getByRole("article")).toHaveCount(0)
})

test("Clipboard and storage failures never announce success", async ({
  page,
}) => {
  await mockCorpus(page)
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: async () => {
          throw new Error("denied")
        },
      },
    })
    Storage.prototype.setItem = () => {
      throw new Error("storage denied")
    }
  })
  await page.goto("/?q=Section%2033(2)(a)")
  await page.getByRole("button", { name: "Copy wording" }).click()
  await expect(
    page.getByText("Clipboard access failed. Please try again."),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Wording copied" }),
  ).toHaveCount(0)
  await page
    .getByRole("button", { name: "Save provision", exact: true })
    .click()
  await expect(
    page.getByText("Your browser could not save this provision."),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Unsave provision" }),
  ).toHaveCount(0)
})

test("Browse uses the published tree and invalid detail never falls back", async ({
  page,
}) => {
  await mockCorpus(page)
  await page.goto("/constitution")
  await page.getByRole("button", { name: /Chapter 4/ }).click()
  await page.getByRole("link", { name: /Section 33\(2\)\(a\)/ }).click()
  await expect(page.getByRole("article")).toContainText(
    provision.authoritative_text,
  )
  await page.route("**/api/v1/legal/provisions/missing**", (route) =>
    route.fulfill({ status: 404, json: { detail: "Not found" } }),
  )
  await page.goto("/constitution/missing")
  await expect(
    page.getByRole("heading", { name: "Provision unavailable" }),
  ).toBeVisible()
  await expect(page.getByRole("article")).toHaveCount(0)
})

test("Saved search has an empty state and unreadable bookmarks are retained", async ({
  page,
}) => {
  await mockCorpus(page)
  await page.goto("/?q=Section%2033(2)(a)")
  await page
    .getByRole("button", { name: "Save provision", exact: true })
    .click()
  await page.goto("/saved")
  await expect(page.getByRole("link", { name: "Open provision" })).toBeVisible()
  await page
    .getByRole("textbox", { name: "Search saved provisions" })
    .fill("unrelated-no-match")
  await expect(
    page.getByRole("heading", { name: "No saved provision matches" }),
  ).toBeVisible()
  await page
    .getByRole("textbox", { name: "Search saved provisions" })
    .fill("defence")
  await expect(page.getByRole("link", { name: "Open provision" })).toBeVisible()
  await page.evaluate(() =>
    localStorage.setItem("law-padi.saved-provisions.v1", "invalid-json"),
  )
  await page.reload()
  await expect(page.getByRole("alert")).toContainText(
    "Their browser data has been retained",
  )
  await page.goto("/?q=Section%2033(2)(a)")
  await page
    .getByRole("button", { name: "Save provision", exact: true })
    .click()
  await expect(
    page.getByText("Your browser could not save this provision."),
  ).toBeVisible()
  expect(
    await page.evaluate(() =>
      localStorage.getItem("law-padi.saved-provisions.v1"),
    ),
  ).toBe("invalid-json")
})
