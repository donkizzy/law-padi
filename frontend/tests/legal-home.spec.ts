import { expect, type Page, test } from "@playwright/test"
import { mockSignedIn } from "./utils/session.ts"

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
  await page.route("**/api/v1/conversations/capabilities", (route) =>
    route.fulfill({
      json: {
        conversations_enabled: false,
        explanations_enabled: false,
        supported_languages: ["English"],
        question_max_length: 2000,
        build_revision: "test",
        prompt_version: "constitution-english-v8",
      },
    }),
  )
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
          "This is the only version of this section available so far.",
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
            "We couldn't find this section in this edition of the Constitution.",
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
            "This section number appears more than once in this edition. Choose the one you mean.",
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
  await page.getByRole("textbox", { name: "Your question" }).fill(query)
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
    await page.goto("/?intent=find")
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
    await expect(article).toContainText("2004 edition")
    await expect(article).not.toContainText(/stored|\bAI\b/i)
    await expect(
      page.getByRole("link", { name: "Chapter 4", exact: true }),
    ).toHaveCount(0)
    await page.getByRole("button", { name: "Copy text" }).click()
    await expect
      .poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toContain(provision.authoritative_text)
    await page.getByRole("button", { name: "Copy link" }).click()
    await expect
      .poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toContain(`?release=${release}`)
    await page.getByRole("button", { name: "Save", exact: true }).click()
    await expect(
      page.getByRole("button", { name: "Remove from saved" }),
    ).toHaveAttribute("aria-pressed", "true")
    await page.getByRole("button", { name: "Original document" }).click()
    const panel = mobile
      ? page.getByRole("dialog", { name: "Section details" })
      : page.getByRole("complementary", { name: "Section details" })
    await expect(panel).toContainText("Page 34")
    await expect(
      panel.getByRole("link", { name: "See it in the original PDF" }),
    ).toHaveAttribute(
      "href",
      /release_version=published-historical-test#page=34/,
    )
    await page.keyboard.press("Escape")
    await expect(panel).not.toBeVisible()
    if (mobile)
      await expect(
        page.getByRole("button", { name: "Original document" }),
      ).toBeFocused()
    await page.getByRole("button", { name: "Version history" }).click()
    await expect(
      page.getByText(
        "This is the only version of this section available so far.",
      ),
    ).toBeVisible()
    await page.reload()
    await expect(
      page.getByRole("button", { name: "Remove from saved" }),
    ).toBeVisible()
    await page.goto("/saved")
    await page.getByRole("link", { name: "Open section" }).click()
    await expect(page).toHaveURL(
      new RegExp(`/constitution/.*release=${release}`),
    )
    await expect(page.getByRole("article")).toContainText(
      provision.authoritative_text,
    )
  })
}

test("Topic queries lead with the top-ranked wording and allow another source", async ({
  page,
}) => {
  await mockCorpus(page)
  const alternative = {
    ...provision,
    canonical_path: "constitution-1999.chapter4.section39",
    provision_version_id: "66666666-6666-4666-8666-666666666666",
    citation: "Section 39",
    heading: "Freedom of expression",
    authoritative_text:
      "Every person shall be entitled to freedom of expression.",
    hybrid_score: 0.01,
  }
  await page.route("**/api/v1/legal/search", (route) =>
    route.fulfill({
      json: {
        ...response("matches", [provision, alternative]),
        retrieval_mode: "hybrid",
      },
    }),
  )
  await page.route("**/api/v1/legal/provisions/**", (route) =>
    route.fulfill({
      json: response("exact", [
        route.request().url().includes("section39") ? alternative : provision,
      ]),
    }),
  )
  await page.goto("/?intent=find")
  await submit(page, "privacy")
  await expect(page.getByRole("heading", { name: "Best match" })).toBeVisible()
  await expect(
    page.getByRole("article", { name: "Constitutional provision" }),
  ).toContainText(provision.authoritative_text)
  await expect(page.getByText(/Retrieval rank|legal-confidence/)).toHaveCount(0)
  await page
    .getByRole("button", { name: /Section 39.*Freedom of expression/ })
    .click()
  await expect(
    page.getByRole("heading", { name: "Selected section" }),
  ).toBeVisible()
  await expect(page.getByRole("article")).toContainText(
    "Every person shall be entitled",
  )
  await page.getByRole("button", { name: "Find related sections" }).click()
  await expect(page.getByRole("heading", { name: "Best match" })).toBeVisible()
  await expect(page.getByRole("article")).toContainText(
    provision.authoritative_text,
  )
})

test("A containing section leads when the first ranked clause is only part of the answer", async ({
  page,
}) => {
  await page.route("**/api/v1/conversations**", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Conversations are not enabled" },
    }),
  )
  await mockCorpus(page)
  const child = {
    ...provision,
    canonical_path: "constitution-1999.chapter6.part1.section131.paragraphd",
    citation: "Section 131(d)",
    authoritative_text:
      "(d) he has been educated up to at least School Certificate level or its equivalent.",
    kind: "paragraph",
    hybrid_score: 0.01639,
  }
  const parent = {
    ...provision,
    canonical_path: "constitution-1999.chapter6.part1.section131",
    provision_version_id: "66666666-6666-4666-8666-666666666666",
    citation: "Section 131",
    authoritative_text: `A person shall be qualified for election to the office of the President if -\n(a) he is a citizen of Nigeria by birth;\n${child.authoritative_text}`,
    kind: "section",
    hybrid_score: 0.01613,
  }
  await page.route("**/api/v1/legal/search", (route) =>
    route.fulfill({
      json: {
        ...response("matches", [child, parent]),
        retrieval_mode: "hybrid",
      },
    }),
  )
  await page.route("**/api/v1/legal/provisions/**", (route) =>
    route.fulfill({
      json: response("exact", [
        route.request().url().includes("paragraphd") ? child : parent,
      ]),
    }),
  )
  await page.goto("/?q=Presidential%20qualifications")
  await expect(page.getByRole("heading", { name: "Best match" })).toBeVisible()
  await expect(page.getByRole("article")).toContainText(
    "citizen of Nigeria by birth",
  )
  await expect(
    page.getByText(/Shown in full so you can read Section 131\(d\) in context/),
  ).toBeVisible()
})

test("Missing, ambiguous, and unsupported references have distinct states", async ({
  page,
}) => {
  await mockCorpus(page)
  await page.goto("/?intent=find")
  await submit(page, "Section 168")
  await expect(
    page.getByRole("heading", { name: "No matching section found" }),
  ).toBeVisible()
  await submit(page, "Section 189")
  await expect(
    page.getByRole("heading", { name: "Which one do you mean?" }),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: /Second printed identity.*page 88/ }),
  ).toBeVisible()
  await submit(page, "Section 33(2)(a)(i)")
  await expect(
    page.getByRole("heading", { name: "Reference not supported" }),
  ).toBeVisible()
})

test("Disabled explanations are disclosed while exact source wording stays available", async ({
  page,
}) => {
  await page.route("**/api/v1/conversations**", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Conversations are not enabled" },
    }),
  )
  await mockCorpus(page)
  await page.goto("/?intent=find")
  await expect(page.getByText(/Plain-English answers are paused/)).toBeVisible()
  await submit(page, "Section 33(2)(a)")
  await expect(page.getByRole("article")).toContainText(
    provision.authoritative_text,
  )
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
              "Search is running in a simpler mode right now, so these keyword matches may be less precise.",
          },
        })
  })
  await page.goto("/?intent=find")
  await submit(page, "privacy")
  await expect(
    page.getByRole("heading", { name: "Search unavailable" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "Try again" }).click()
  await expect(
    page.getByText(/keyword matches may be less precise/),
  ).toBeVisible()
  await expect(page.getByRole("heading", { name: "Best match" })).toBeVisible()
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
  await expect(page.getByText("Searching the Constitution…")).toBeVisible()
  await submit(page, "Section 33(2)(a)")
  await expect(page.getByRole("article")).toBeVisible()
  finish?.()
  await expect(page.getByText("Obsolete answer")).toHaveCount(0)
  await page
    .getByRole("button", { name: "New conversation", exact: true })
    .first()
    .click()
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
  await page.getByRole("button", { name: "Copy text" }).click()
  await expect(page.getByText("Couldn't copy. Please try again.")).toBeVisible()
  await expect(page.getByRole("button", { name: "Text copied" })).toHaveCount(0)
  await page.getByRole("button", { name: "Save", exact: true }).click()
  await expect(page.getByText("Couldn't save on this device.")).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Remove from saved" }),
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
  await page.getByRole("button", { name: "Save", exact: true }).click()
  await page.goto("/saved")
  await expect(page.getByRole("link", { name: "Open section" })).toBeVisible()
  await page
    .getByRole("textbox", { name: "Search saved sections" })
    .fill("unrelated-no-match")
  await expect(
    page.getByRole("heading", { name: "Nothing matches that search" }),
  ).toBeVisible()
  await page
    .getByRole("textbox", { name: "Search saved sections" })
    .fill("defence")
  await expect(page.getByRole("link", { name: "Open section" })).toBeVisible()
  await page.evaluate(() =>
    localStorage.setItem("law-padi.saved-provisions.v1", "invalid-json"),
  )
  await page.reload()
  await expect(page.getByRole("alert")).toContainText(
    "Their browser data has been retained",
  )
  await page.goto("/?q=Section%2033(2)(a)")
  await page.getByRole("button", { name: "Save", exact: true }).click()
  await expect(page.getByText("Couldn't save on this device.")).toBeVisible()
  expect(
    await page.evaluate(() =>
      localStorage.getItem("law-padi.saved-provisions.v1"),
    ),
  ).toBe("invalid-json")
})

test("Browse search always finds sections even when chat is available", async ({
  page,
}) => {
  await mockCorpus(page)
  let createdConversations = 0
  await page.route("**/api/v1/conversations**", (route) => {
    const request = route.request()
    if (new URL(request.url()).pathname.endsWith("/capabilities"))
      return route.fulfill({
        json: {
          conversations_enabled: true,
          explanations_enabled: true,
          supported_languages: ["English"],
          question_max_length: 2000,
          build_revision: "test",
          prompt_version: "constitution-english-v8",
        },
      })
    if (request.method() === "POST") createdConversations += 1
    return route.fulfill({ json: { data: [], count: 0 } })
  })
  await page.goto("/constitution")
  await page
    .getByRole("textbox", { name: "Search the Constitution" })
    .fill("Section 33(2)(a)")
  await page.getByRole("button", { name: "Search", exact: true }).click()
  await expect(
    page.getByRole("article", { name: "Constitutional provision" }),
  ).toContainText(provision.authoritative_text)
  await expect(
    page.getByText(provision.authoritative_text, { exact: true }),
  ).toBeInViewport()
  await expect(page).toHaveURL(/intent=find/)
  expect(createdConversations).toBe(0)
})

for (const mobile of [false, true]) {
  test(`${mobile ? "Mobile" : "Desktop"}: a delayed search brings the loaded section into view`, async ({
    page,
  }) => {
    await page.setViewportSize(
      mobile ? { width: 390, height: 844 } : { width: 1280, height: 720 },
    )
    await mockCorpus(page)
    let finishSearch!: () => void
    const loading = new Promise<void>((resolve) => {
      finishSearch = resolve
    })
    await page.route("**/api/v1/legal/search", async (route) => {
      await loading
      await route.fulfill({ json: response("exact", [provision]) })
    })
    await page.goto("/?q=Section%2033(2)(a)&intent=find")
    await expect(
      page.getByText("Searching the Constitution…", { exact: true }),
    ).toBeVisible()
    finishSearch()
    await expect(
      page.getByText(provision.authoritative_text, { exact: true }),
    ).toBeInViewport()
    await expect(
      page.getByRole("region", { name: "Search results" }),
    ).toBeFocused()
  })
}

test("guests landing on the home URL see the welcome page first", async ({
  page,
}) => {
  await page.goto("/")
  await expect(page).toHaveURL(/\/welcome$/)
  await page
    .locator('a[href="/"]', { hasText: "Ask a question" })
    .last()
    .click()
  await expect(page).toHaveURL(/\/(\?.*)?$/)
  await expect(page).not.toHaveURL(/\/welcome/)
})

test("signed-in visitors landing on the home URL go straight to the app", async ({
  page,
}) => {
  await mockSignedIn(page)
  await page.goto("/")
  await expect(page).not.toHaveURL(/\/welcome/)
})

test("the privacy notice is linked from the welcome page and sign-up", async ({
  page,
}) => {
  await page.goto("/welcome")
  await page
    .getByRole("navigation", { name: "Footer" })
    .getByRole("link", { name: "Privacy" })
    .click()
  await expect(
    page.getByRole("heading", { name: "How we handle your data." }),
  ).toBeVisible()
  await expect(
    page.getByText("deleted after 30 days without use"),
  ).toBeVisible()

  await page.goto("/signup")
  await page.getByRole("link", { name: "how we handle your data" }).click()
  await expect(page).toHaveURL(/\/privacy$/)
})
