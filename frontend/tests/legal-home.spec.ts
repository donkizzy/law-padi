import { expect, type Page, test } from "@playwright/test"
import type {
  LegalSearchResponse,
  LegalSearchResult,
  ProvisionKind,
} from "../src/client"
import { chatCapabilities, conversationList } from "./fixtures/chat.ts"
import {
  currentRelease,
  legalInstrument,
  legalInstruments,
  legalSearchResponse,
  legalSearchResult,
  provisionReference,
  provisionTree,
} from "./fixtures/legal.ts"
import {
  mockChatShell,
  mockCurrentRelease,
  mockInstruments,
} from "./fixtures/shell.ts"
import { mockSignedIn } from "./utils/session.ts"

const release = "published-historical-test"
const path = "constitution-1999.chapter4.section33.subsection2.paragrapha"
const reference = (
  canonical_path: string,
  kind: ProvisionKind,
  citation: string,
  has_text = true,
) =>
  provisionReference({
    canonical_path,
    kind,
    number: citation,
    heading: citation,
    citation,
    has_text,
    authoritative_text: has_text ? "Parent context retained separately." : null,
  })
const provision = legalSearchResult({
  canonical_path: path,
  citation: "Section 33(2)(a)",
  heading: "Defence from unlawful violence",
  ancestor_headings: ["Fundamental Rights"],
  authoritative_text:
    "(a) for the defence of any person from unlawful violence or for the defence of property;",
  source_page_start: 34,
  source_page_end: 34,
  release_version: release,
  kind: "paragraph",
  ancestors: [
    reference("constitution-1999.chapter4", "chapter", "Chapter 4", false),
    reference("constitution-1999.chapter4.section33", "section", "Section 33"),
    reference(
      "constitution-1999.chapter4.section33.subsection2",
      "subsection",
      "Section 33(2)",
    ),
  ],
})
const response = (
  outcome: LegalSearchResponse["outcome"] = "exact",
  data = [provision],
  message: string | null = null,
) => legalSearchResponse({ data, outcome, message, release_version: release })

test.use({ storageState: { cookies: [], origins: [] } })

async function mockCorpus(page: Page) {
  await page.route("**/api/v1/conversations/capabilities", (route) =>
    route.fulfill({
      json: chatCapabilities({
        conversations_enabled: false,
        explanations_enabled: false,
      }),
    }),
  )
  await page.route("**/api/v1/legal/**", async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith("/instruments"))
      return route.fulfill({
        json: legalInstruments(
          [
            legalInstrument({
              title: "Constitution",
              short_title: "Constitution",
              edition_note: "Later amendments may differ.",
            }),
          ],
          release,
        ),
      })
    if (url.pathname.endsWith("/releases/current"))
      return route.fulfill({
        json: currentRelease({ release_version: release }),
      })
    if (url.pathname.endsWith("/provision-history"))
      return route.fulfill({
        json: response(
          "exact",
          [provision],
          "This is the only version of this section available so far.",
        ),
      })
    if (url.pathname.endsWith("/provisions/tree")) {
      const chapter = reference(
        "constitution-1999.chapter4",
        "chapter",
        "Chapter 4",
        false,
      )
      const children = url.searchParams.has("parent_path")
      return route.fulfill({
        json: provisionTree({
          data: children
            ? [reference(path, "paragraph", provision.citation)]
            : [chapter],
          parent: children ? chapter : null,
          release_version: release,
        }),
      })
    }
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

// The pages that need no corpus fixtures still load the chat capabilities, the
// current release and the instrument list.
async function mockShell(page: Page) {
  await mockChatShell(page)
  await mockCurrentRelease(page, { release_version: release })
  await mockInstruments(page, [legalInstrument()], release)
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
    ).toHaveAttribute(
      "href",
      `/laws/constitution-1999?parent=constitution-1999.chapter4&release=${release}`,
    )
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
      new RegExp(`/laws/constitution-1999/.*release=${release}`),
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
      } satisfies LegalSearchResponse,
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
  const child: LegalSearchResult = {
    ...provision,
    canonical_path: "constitution-1999.chapter6.part1.section131.paragraphd",
    citation: "Section 131(d)",
    authoritative_text:
      "(d) he has been educated up to at least School Certificate level or its equivalent.",
    kind: "paragraph",
    hybrid_score: 0.01639,
  }
  const parent: LegalSearchResult = {
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
      } satisfies LegalSearchResponse,
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
          } satisfies LegalSearchResponse,
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
  await expect(page.getByText("Searching the published laws…")).toBeVisible()
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
  await page.getByRole("link", { name: /Chapter 4/ }).click()
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
    localStorage.setItem("constitution-ng.saved-provisions.v2", "invalid-json"),
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
      localStorage.getItem("constitution-ng.saved-provisions.v2"),
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
        json: chatCapabilities(),
      })
    if (request.method() === "POST") createdConversations += 1
    return route.fulfill({ json: conversationList() })
  })
  await page.goto("/constitution")
  await page
    .getByRole("textbox", { name: "Search this law" })
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
      page.getByText("Searching the published laws…", { exact: true }),
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
  await mockShell(page)
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
  await mockShell(page)
  await mockSignedIn(page)
  await page.goto("/")
  await expect(page).not.toHaveURL(/\/welcome/)
})

test("the privacy notice is linked from the welcome page and sign-up", async ({
  page,
}) => {
  await mockShell(page)
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

test("Public provision metadata stays unique after browser rendering", async ({
  page,
}) => {
  await mockCorpus(page)
  await page.goto(`/constitution/${path}?release=${release}`)
  await expect(
    page.getByRole("article", { name: "Constitutional provision" }),
  ).toContainText(provision.authoritative_text)
  await expect(page.locator("title")).toHaveCount(1)
  await expect(page.locator('meta[name="description"]')).toHaveCount(1)
  await expect(page.locator('link[rel="canonical"]')).toHaveCount(1)
  await expect(page.locator("h1")).toHaveCount(1)
  await expect(page).toHaveTitle(/Section 33\(2\)\(a\).*2004 source edition/)
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    "href",
    new RegExp(`release=${release}`),
  )
  const types = await page
    .locator('script[type="application/ld+json"]')
    .allTextContents()
  expect(
    types.some((item) => JSON.parse(item)["@type"] === "BreadcrumbList"),
  ).toBe(true)
})

test("Amendments and publisher pages disclose their actual public scope", async ({
  page,
}) => {
  await mockCorpus(page)
  await page.goto("/amendments")
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Amendments are not published here yet",
  )
  await expect(page.getByText("First Alteration Act, 2010")).toHaveCount(0)
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
    "content",
    /noindex/,
  )
  await page.goto("/about")
  await expect(
    page.getByRole("heading", { name: "About constitution.ng", exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole("link", {
      name: "Corrections on GitHub (repository access required)",
    }),
  ).toHaveAttribute("href", "https://github.com/donkizzy/law-padi/issues")
  await page.screenshot({
    path: "../output/playwright/seo-about.png",
    fullPage: true,
  })
})

test("A translated search says what was searched and translates server messages", async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem(
      "constitution-ng.preferences.v1",
      JSON.stringify({ language: "yoruba" }),
    ),
  )
  await mockCorpus(page)
  await page.route("**/api/v1/legal/search", (route) =>
    route.fulfill({
      json: {
        ...response("matches"),
        retrieval_mode: "lexical",
        message:
          "Search is running in a simpler mode right now, so these keyword matches may be less precise.",
        message_code: "simpler_search",
        query_language: "yo",
        searched_query: "Can police search my phone?",
      } satisfies LegalSearchResponse,
    }),
  )
  await page.goto(`/?q=${encodeURIComponent("Ṣé ọlọ́pàá lè yẹ fóònù mi wò?")}`)
  await expect(
    page.getByText("A wá a ní èdè Gẹ̀ẹ́sì báyìí: Can police search my phone?"),
  ).toBeVisible()
  await expect(
    page.getByText(
      "Ìwádìí ń ṣiṣẹ́ ní ọ̀nà tó rọrùn báyìí, nítorí náà àwọn èsì wọ̀nyí lè má péye tó.",
    ),
  ).toBeVisible()
})

test("Uncorroborated results show a warning and neutral match heading", async ({
  page,
}) => {
  await mockCorpus(page)
  await page.route("**/api/v1/legal/search", (route) =>
    route.fulfill({
      json: {
        ...response("matches"),
        message:
          "The published provisions don't seem to answer this directly. These are the closest sections we found.",
        message_code: "not_covered",
      } satisfies LegalSearchResponse,
    }),
  )
  await page.goto("/?intent=find&q=Who+won+the+World+Cup", {
    waitUntil: "domcontentloaded",
  })
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "don't seem to answer this directly" }),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "Search matches", exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "Best match", exact: true }),
  ).toHaveCount(0)
})

test("An English search shows the server message as sent", async ({ page }) => {
  await mockCorpus(page)
  await page.route("**/api/v1/legal/search", (route) =>
    route.fulfill({
      json: {
        ...response("matches"),
        message: "We found some of these sections, but not all of them.",
        message_code: "partial_sections",
        query_language: "en",
        searched_query: null,
      } satisfies LegalSearchResponse,
    }),
  )
  await page.goto("/?q=privacy")
  await expect(
    page.getByText("We found some of these sections, but not all of them."),
  ).toBeVisible()
  await expect(page.getByText(/Searched in English for/)).toHaveCount(0)
})
