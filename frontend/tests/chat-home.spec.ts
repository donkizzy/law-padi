import { readFile } from "node:fs/promises"
import { expect, type Page, test } from "@playwright/test"
import type {
  CitationOutcome,
  EvidenceItem,
  MessagePublic,
} from "../src/client"
import { type ChatAnswer, chatAnswer } from "./fixtures/chat.ts"
import { mockSignedIn } from "./utils/session.ts"

const conversationId = "11111111-1111-4111-8111-111111111111"
const runId = "22222222-2222-4222-8222-222222222222"
const releaseVersion = "published-historical-test"
const editionLabel = "Historical/source Constitution compilation (LFN 2004)"
const question = "What does Section 37 protect?"
const evidence: EvidenceItem = {
  evidence_id: "E1",
  provision_id: "33333333-3333-4333-8333-333333333333",
  provision_version_id: "44444444-4444-4444-8444-444444444444",
  canonical_path: "constitution-1999.chapter4.section37",
  citation: "Section 37",
  authoritative_text:
    "The privacy of citizens, their homes, correspondence, telephone conversations and telegraphic communications is hereby guaranteed and protected.",
  text_sha256: "test-hash",
  ancestor_citations: ["Chapter 4"],
  legal_status: "historical",
  edition_label: editionLabel,
  release_id: "55555555-5555-4555-8555-555555555555",
  release_version: releaseVersion,
  source_document_id: "66666666-6666-4666-8666-666666666666",
  source_title: "Constitution compilation",
  source_authority: "Retained source authority",
  source_url: "https://example.test/constitution.pdf",
  source_content_url: `/api/v1/legal/sources/66666666-6666-4666-8666-666666666666/content?release_version=${releaseVersion}`,
  source_page_start: 39,
  source_page_end: 39,
}
const outcome: CitationOutcome = {
  reference: "Section 37",
  status: "resolved",
  evidence_ids: ["E1"],
  message: null,
}
const answer = chatAnswer({
  blocks: [
    {
      text: "The Constitution protects privacy in homes and communications.",
      evidence_ids: ["E1"],
      quotation: null,
    },
  ],
  citation_outcomes: [outcome],
  evidence: [evidence],
})
const conversation = {
  id: conversationId,
  title: question,
  release_version: releaseVersion,
  edition_label: editionLabel,
  created_at: "2026-10-08T08:00:00Z",
  updated_at: "2026-10-08T08:00:00Z",
}

test.use({ storageState: { cookies: [], origins: [] } })

async function mockChat(
  page: Page,
  deliveredAnswer: ChatAnswer = answer,
  options: {
    acceptance?: Promise<void>
    events?: Promise<void>
    failedSubmissions?: number
    historyFailures?: number
    interruptStream?: boolean
    answerLanguages?: string[]
  } = {},
) {
  let created = false
  let submitted = false
  let completed = false
  let createCount = 0
  let failureCount = options.failedSubmissions ?? 0
  let historyFailures = options.historyFailures ?? 0
  const submissions: Array<{
    question: string
    idempotency_key: string
    selected_provision_version_id?: string | null
    answer_language?: string | null
  }> = []
  await page.route("**/api/v1/legal/search", (route) =>
    route.fulfill({
      json: {
        data: [],
        count: 0,
        outcome: "not_found",
        retrieval_mode: "exact",
        release_version: releaseVersion,
        edition_label: editionLabel,
        citation_outcomes: [outcome],
        evidence: [evidence],
        message: null,
      },
    }),
  )
  await page.route("**/api/v1/conversations**", async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path.endsWith("/capabilities"))
      return route.fulfill({
        json: {
          conversations_enabled: true,
          explanations_enabled: true,
          supported_languages: ["English"],
          answer_languages: options.answerLanguages ?? ["en"],
          question_max_length: 2000,
          build_revision: "test",
          prompt_version: "constitution-english-v8",
        },
      })
    if (path.endsWith(`/conversations/${conversationId}/events`)) {
      if (options.events) await options.events
      expect(new URL(request.url()).searchParams.get("run_id")).toBe(runId)
      completed = true
      const events = [
        {
          id: 1,
          event: "retrieval.complete",
          data: { evidence: [evidence], citation_outcomes: [outcome] },
        },
        ...(options.interruptStream
          ? []
          : [
              {
                id: 2,
                event: "answer.complete",
                data: { answer: deliveredAnswer },
              },
            ]),
      ]
      return route.fulfill({
        contentType: "text/event-stream",
        body: events
          .map(
            ({ id, event, data }) =>
              `id: ${id}\nevent: ${event}\ndata: ${JSON.stringify(data)}\n\n`,
          )
          .join(""),
      })
    }
    if (
      path.endsWith(`/conversations/${conversationId}/messages`) &&
      request.method() === "POST"
    ) {
      submissions.push(request.postDataJSON())
      if (failureCount-- > 0)
        return route.fulfill({
          status: 503,
          json: { detail: "Explanations are temporarily unavailable" },
        })
      if (options.acceptance) await options.acceptance
      submitted = true
      completed = false
      return route.fulfill({
        status: 202,
        json: {
          run_id: runId,
          user_message_id: "77777777-7777-4777-8777-777777777777",
          status: "pending",
        },
      })
    }
    if (
      path.endsWith(`/conversations/${conversationId}`) &&
      request.method() === "GET"
    ) {
      const messages: MessagePublic[] = submitted
        ? [
            {
              id: "77777777-7777-4777-8777-777777777777",
              role: "user",
              content: question,
              answer_status: null,
              answer_content: null,
              evidence_snapshot: null,
              created_at: "2026-10-08T08:00:01Z",
            },
          ]
        : []
      if (completed)
        messages.push({
          id: "88888888-8888-4888-8888-888888888888",
          role: "assistant",
          content: "",
          answer_status: "completed",
          answer_content: deliveredAnswer,
          evidence_snapshot: [evidence],
          created_at: "2026-10-08T08:00:02Z",
        })
      return route.fulfill({
        json: {
          ...conversation,
          messages,
          active_run_id: submitted && !completed ? runId : null,
        },
      })
    }
    if (path.endsWith("/conversations") && request.method() === "POST") {
      created = true
      createCount += 1
      return route.fulfill({ status: 201, json: conversation })
    }
    if (path.endsWith("/conversations") && request.method() === "GET") {
      if (historyFailures-- > 0)
        return route.fulfill({
          status: 503,
          json: { detail: "History unavailable" },
        })
      return route.fulfill({
        json: {
          data: created ? [conversation] : [],
          count: created ? 1 : 0,
        },
      })
    }
    if (path.endsWith("/feedback"))
      return route.fulfill({
        json: {
          message_id: "88888888-8888-4888-8888-888888888888",
          helpful: request.postDataJSON().helpful,
          updated_at: "2026-10-13T12:00:00Z",
        },
      })
    return route.fulfill({ status: 404, json: { detail: "Not found" } })
  })
  return {
    submissions,
    get createCount() {
      return createCount
    },
  }
}

for (const mobile of [false, true]) {
  test(`${mobile ? "Mobile" : "Desktop"}: saved chat, SSE answer, and source navigation`, async ({
    page,
  }) => {
    await page.setViewportSize(
      mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
    )
    const mock = await mockChat(page)
    await page.goto("/?intent=ask")
    await expect(
      page.getByRole("heading", { name: "Ask about Nigeria's laws." }),
    ).toBeVisible()
    await page.getByRole("textbox", { name: "Your question" }).fill(question)
    await page.getByRole("button", { name: "Send question" }).click()
    await expect(
      page.getByRole("region", { name: "Answer", exact: true }),
    ).toContainText("protects privacy")
    const explanation = page.getByRole("region", {
      name: "Answer",
      exact: true,
    })
    await expect(explanation).not.toContainText(/\bAI\b|stored wording/i)
    await expect(explanation).toContainText(
      "This is the 1999 Constitution as published in 2004.",
    )
    const answerTop = await explanation
      .getByText(/Constitution protects privacy/)
      .evaluate((element) => element.getBoundingClientRect().top)
    const evidenceTop = await explanation
      .getByRole("heading", { name: "Sections used" })
      .evaluate((element) => element.getBoundingClientRect().top)
    expect(answerTop).toBeLessThan(evidenceTop)
    expect(mock.submissions).toHaveLength(1)
    expect(mock.submissions[0].idempotency_key).toBeTruthy()

    await page
      .getByRole("region", { name: "Answer", exact: true })
      .getByRole("button", { name: "Section 37", exact: true })
      .click()
    if (mobile)
      await expect(
        page.getByRole("dialog", { name: "Section details" }),
      ).toContainText(evidence.authoritative_text)
    else
      await expect(
        page.getByRole("complementary", { name: "Section details" }),
      ).toContainText(evidence.authoritative_text)
    await expect(
      page.getByRole("link", { name: "Open full section" }),
    ).toHaveAttribute(
      "href",
      `/laws/constitution-1999/${evidence.canonical_path}?release=${releaseVersion}`,
    )
    await page.getByRole("button", { name: "Explain this section" }).click()
    await expect.poll(() => mock.submissions.length).toBe(2)
    expect(mock.submissions[1]).toMatchObject({
      question: "Section 37",
      selected_provision_version_id: evidence.provision_version_id,
    })
    await page.reload()
    await expect(
      page.getByRole("region", { name: "Answer", exact: true }),
    ).toContainText("protects privacy")
    await expect(
      page.getByText(question, { exact: true }).first(),
    ).toBeVisible()
  })
}

test("A withheld topic explanation leads with complete parent source wording", async ({
  page,
}) => {
  const child = {
    ...evidence,
    canonical_path: "constitution-1999.chapter6.part1.section131.paragraphd",
    citation: "Section 131(d)",
    authoritative_text:
      "(d) he has been educated up to at least School Certificate level or its equivalent.",
  }
  const parent = {
    ...evidence,
    evidence_id: "E2",
    provision_version_id: "77777777-7777-4777-8777-777777777777",
    canonical_path: "constitution-1999.chapter6.part1.section131",
    citation: "Section 131",
    authoritative_text: `A person shall be qualified for election to the office of the President if -\n(a) he is a citizen of Nigeria by birth;\n${child.authoritative_text}`,
  }
  await mockChat(page, {
    ...answer,
    outcome: "validation_failed",
    blocks: [],
    citation_outcomes: [],
    evidence: [child, parent],
    notice: "We couldn't write an explanation.",
  })
  await page.goto("/?intent=ask")
  await page.getByRole("textbox", { name: "Your question" }).fill(question)
  await page.getByRole("button", { name: "Send question" }).click()
  const region = page.getByRole("region", { name: "Answer", exact: true })
  await expect(region.getByRole("status")).toContainText(
    "We couldn't write an explanation.",
  )
  await expect(region).toContainText("Section 131")
  await expect(region).toContainText("citizen of Nigeria by birth")
  await expect(
    region.getByRole("button", { name: "More about this section" }),
  ).toBeVisible()
})

test("An answer leads with plain English, lists items, and offers follow-ups", async ({
  page,
}) => {
  const followUp = "What can I do if my privacy is violated?"
  const mock = await mockChat(page, {
    ...answer,
    blocks: [
      {
        text: "Generally, yes. The Constitution protects your privacy.",
        evidence_ids: ["E1"],
        quotation: null,
      },
      {
        text: "It covers:\n- your home\n- your correspondence\n- your phone conversations",
        evidence_ids: ["E1"],
        quotation: null,
      },
    ],
    missing_facts: ["Whether a court order allowed the search"],
    related_laws: ["Police Act 2020 (police powers, including searches)"],
    follow_up_questions: [followUp],
  })
  await page.goto("/?intent=ask")
  await page.getByRole("textbox", { name: "Your question" }).fill(question)
  await page.getByRole("button", { name: "Send question" }).click()
  const region = page.getByRole("region", { name: "Answer", exact: true })
  await expect(region.getByRole("listitem")).toHaveText([
    "your home",
    "your correspondence",
    "your phone conversations",
    "Whether a court order allowed the search",
    "Police Act 2020 (police powers, including searches)",
  ])
  await expect(region).toContainText("The answer may depend on")
  await expect(
    region.getByRole("region", { name: "Other laws also apply" }),
  ).toBeVisible()
  // Both blocks cite Section 37; its button shows once.
  await expect(
    region.getByRole("button", { name: "Section 37", exact: true }),
  ).toHaveCount(1)
  await region.getByRole("button", { name: followUp }).click()
  await expect.poll(() => mock.submissions.length).toBe(2)
  expect(mock.submissions[1].question).toBe(followUp)
})

test("Logout clears private conversation data and drafts in another tab", async ({
  page,
}) => {
  const context = page.context()
  const otherTab = await context.newPage()
  await context.route("**/api/v1/users/me", (route) =>
    route.fulfill({
      json: {
        id: "99999999-9999-4999-8999-999999999999",
        email: "account@example.test",
        full_name: "Test Account",
        is_active: true,
        is_superuser: false,
      },
    }),
  )
  await context.route("**/api/v1/conversations**", (route) => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith("/capabilities"))
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
    const authenticated =
      route.request().headers().authorization === "Bearer account-token"
    if (path.endsWith(`/${conversationId}`))
      return authenticated
        ? route.fulfill({
            json: {
              ...conversation,
              messages: [
                {
                  id: "77777777-7777-4777-8777-777777777777",
                  role: "user",
                  content: "Private account question",
                  created_at: conversation.created_at,
                },
              ],
            },
          })
        : route.fulfill({ status: 404, json: { detail: "Not found" } })
    return route.fulfill({
      json: {
        data: authenticated
          ? [{ ...conversation, title: "Private account conversation" }]
          : [],
        count: authenticated ? 1 : 0,
      },
    })
  })
  await mockSignedIn(page)
  await mockSignedIn(otherTab)
  await page.goto("/?intent=ask")
  await otherTab.goto(`/?intent=ask&c=${conversationId}`)
  await expect(otherTab.getByText("Private account question")).toBeVisible()
  await otherTab
    .getByRole("textbox", { name: "Your question" })
    .fill("Private draft")
  await expect(page.getByText("Private account conversation")).toBeVisible()
  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log Out" }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto("/?intent=ask")
  await expect(page.getByText("Private account conversation")).toHaveCount(0)
  await expect(page.getByText("Your chats will appear here.")).toBeVisible()
  await expect(otherTab.getByText("Private account question")).toHaveCount(0)
  await expect(otherTab.getByText("Private account conversation")).toHaveCount(
    0,
  )
  await expect(
    otherTab.getByRole("textbox", { name: "Your question" }),
  ).toHaveValue("")
  expect(
    await otherTab.evaluate(() => Object.values(sessionStorage)),
  ).not.toContain("Private draft")
})

async function sendQuestion(page: Page) {
  await page.getByRole("textbox", { name: "Your question" }).fill(question)
  await page.getByRole("button", { name: "Send question" }).click()
}

async function newConversation(page: Page) {
  const menu = page.getByRole("button", { name: "Open Sidebar", exact: true })
  if ((page.viewportSize()?.width ?? 1440) < 768) await menu.click()
  await page
    .getByRole("button", { name: "New conversation", exact: true })
    .first()
    .click()
}

for (const mobile of [false, true]) {
  test(`${mobile ? "Mobile" : "Desktop"}: New clears a completed answer and source, closes navigation, and focuses the editor`, async ({
    page,
  }) => {
    await page.setViewportSize(
      mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
    )
    await mockChat(page)
    await page.goto("/?intent=ask")
    await sendQuestion(page)
    await expect(
      page.getByRole("region", { name: "Answer", exact: true }),
    ).toBeVisible()
    await expect(
      page.getByText(answer.blocks[0].text, { exact: true }),
    ).toBeInViewport()
    await page.getByRole("button", { name: "Section 37", exact: true }).click()
    if (mobile)
      await page.getByRole("button", { name: "Close", exact: true }).click()
    await newConversation(page)
    await expect(page).not.toHaveURL(/(?:[?&])c=/)
    await expect(
      page.getByRole("region", { name: "Answer", exact: true }),
    ).toHaveCount(0)
    await expect(
      page.getByRole("complementary", { name: "Section details" }),
    ).toHaveCount(0)
    await expect(
      page.getByRole("dialog", { name: "Sidebar" }),
    ).not.toBeVisible()
    const editor = page.getByRole("textbox", { name: "Your question" })
    await expect(editor).toBeEnabled()
    await expect(editor).toBeEmpty()
    await expect(editor).toBeFocused()
  })
}

test("Sidebar search and collapse preserve navigation alignment", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await mockChat(page)
  await page.goto("/?intent=ask")
  await sendQuestion(page)
  await expect(
    page.getByRole("region", { name: "Answer", exact: true }),
  ).toBeVisible()
  const sidebar = page.locator('[data-slot="sidebar-inner"]')
  const newChat = sidebar.getByRole("button", {
    name: "New conversation",
    exact: true,
  })
  const find = sidebar.getByRole("link", {
    name: "Find a section",
    exact: true,
  })
  const iconCenter = (locator: typeof find) =>
    locator.locator("svg").evaluate((element) => {
      const rect = element.getBoundingClientRect()
      return rect.x + rect.width / 2
    })
  expect(
    await newChat.evaluate((element) => element.getBoundingClientRect().x),
  ).toBe(await find.evaluate((element) => element.getBoundingClientRect().x))
  await page.screenshot({ path: testInfo.outputPath("sidebar-expanded.png") })

  const searchButton = sidebar.getByRole("button", {
    name: "Search conversations",
  })
  const search = sidebar.getByRole("textbox", { name: "Search conversations" })
  await expect(search).toBeHidden()
  await searchButton.click()
  await expect(search).toBeFocused()
  await search.fill("privacy")
  await search.press("Escape")
  await expect(searchButton).toBeFocused()
  await searchButton.click()
  await expect(search).toHaveValue("")
  await sidebar.getByRole("button", { name: "Close", exact: true }).click()

  await sidebar.getByRole("button", { name: "Collapse Sidebar" }).click()
  await expect(
    page.locator('[data-slot="sidebar"][data-state="collapsed"]'),
  ).toBeVisible()
  await expect(page.locator('[data-slot="sidebar-container"]')).toHaveCSS(
    "width",
    "48px",
  )
  expect(await iconCenter(newChat)).toBe(await iconCenter(find))
  expect(
    await iconCenter(sidebar.getByRole("button", { name: "Open Sidebar" })),
  ).toBe(await iconCenter(find))
  await expect(searchButton).toBeHidden()
  await page.screenshot({ path: testInfo.outputPath("sidebar-collapsed.png") })
  await sidebar.getByRole("button", { name: "Open Sidebar" }).click()
  await expect(searchButton).toBeVisible()
})

test("Answer loading rotates research phrases and respects reduced motion", async ({
  page,
}, testInfo) => {
  let releaseEvents!: () => void
  const events = new Promise<void>((resolve) => {
    releaseEvents = resolve
  })
  await page.clock.install()
  await page.emulateMedia({ reducedMotion: "reduce" })
  await mockChat(page, answer, { events })
  await page.goto("/?intent=ask")
  await sendQuestion(page)
  const pending = page.getByRole("region", { name: "Answer in progress" })
  await expect(
    pending.getByText("Consulting the text…", { exact: true }),
  ).toBeVisible()
  await page.clock.pauseAt(new Date())
  await page.clock.runFor(4000)
  await expect(
    pending.getByText("Tracing the provisions…", { exact: true }),
  ).toBeVisible()
  await expect(pending.getByText("4s", { exact: true })).toBeVisible()
  await expect(pending.locator(".answer-loading-pixel").first()).toHaveCSS(
    "animation-name",
    "none",
  )
  await page.screenshot({ path: testInfo.outputPath("answer-loading.png") })
  releaseEvents()
  await expect(
    page.getByRole("region", { name: "Answer", exact: true }),
  ).toBeVisible()
  await expect(pending).toHaveCount(0)
})

test("New detaches an active answer without disabling the new editor", async ({
  page,
}) => {
  let releaseEvents!: () => void
  const events = new Promise<void>((resolve) => {
    releaseEvents = resolve
  })
  await mockChat(page, answer, { events })
  await page.goto("/?intent=ask")
  await sendQuestion(page)
  await expect(
    page.getByRole("button", { name: "Stop answering" }),
  ).toBeVisible()
  await newConversation(page)
  await expect(
    page.getByRole("textbox", { name: "Your question" }),
  ).toBeEnabled()
  releaseEvents()
  await expect(
    page.getByRole("region", { name: "Answer", exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: "Stop answering" }),
  ).toHaveCount(0)
})

test("A late acceptance cannot navigate away from New", async ({ page }) => {
  let releaseAcceptance!: () => void
  const acceptance = new Promise<void>((resolve) => {
    releaseAcceptance = resolve
  })
  const mock = await mockChat(page, answer, { acceptance })
  await page.goto("/?intent=ask")
  await sendQuestion(page)
  await expect.poll(() => mock.submissions.length).toBe(1)
  await newConversation(page)
  const freshUrl = page.url()
  releaseAcceptance()
  await expect(
    page.getByRole("textbox", { name: "Your question" }),
  ).toBeEnabled()
  await expect(page).toHaveURL(freshUrl)
  await expect(
    page.getByRole("region", { name: "Answer", exact: true }),
  ).toHaveCount(0)
})

test("Retry preserves the question, created conversation and idempotency key", async ({
  page,
}) => {
  const mock = await mockChat(page, answer, { failedSubmissions: 1 })
  await page.goto("/?intent=ask")
  await sendQuestion(page)
  await expect(page.getByRole("alert")).toContainText("temporarily unavailable")
  await expect(
    page.getByRole("textbox", { name: "Your question" }),
  ).toHaveValue(question)
  await page.getByRole("button", { name: "Retry question" }).click()
  await expect(
    page.getByRole("region", { name: "Answer", exact: true }),
  ).toBeVisible()
  expect(mock.createCount).toBe(1)
  expect(mock.submissions).toHaveLength(2)
  expect(mock.submissions[0].idempotency_key).toBe(
    mock.submissions[1].idempotency_key,
  )
})

test("Persisted completion recovers when the terminal SSE event is lost", async ({
  page,
}) => {
  await mockChat(page, answer, { interruptStream: true })
  await page.goto("/?intent=ask")
  await sendQuestion(page)
  await expect(
    page.getByRole("region", { name: "Answer", exact: true }),
  ).toContainText("protects privacy")
  await expect(
    page.getByRole("textbox", { name: "Your question" }),
  ).toBeEnabled()
})

test("A history failure does not change Ask into Find", async ({ page }) => {
  await mockChat(page, answer, { historyFailures: 2 })
  await page.goto("/?intent=ask")
  await expect(
    page.getByRole("heading", { name: "Ask about Nigeria's laws." }),
  ).toBeVisible()
  await expect(page.getByRole("alert")).toContainText("History couldn't load")
  await expect(
    page.getByRole("textbox", { name: "Your question" }),
  ).toBeEnabled()
})

test("Draft survives reload and New clears it even when already on an empty chat", async ({
  page,
}) => {
  await mockChat(page)
  await page.goto("/?intent=ask")
  await page
    .getByRole("textbox", { name: "Your question" })
    .fill("My unfinished question")
  await page.reload()
  await expect(
    page.getByRole("textbox", { name: "Your question" }),
  ).toHaveValue("My unfinished question")
  await newConversation(page)
  await expect(page.getByRole("textbox", { name: "Your question" })).toBeEmpty()
  const first = page.url()
  await page
    .getByRole("textbox", { name: "Your question" })
    .fill("Another draft")
  await newConversation(page)
  await expect(page.getByRole("textbox", { name: "Your question" })).toBeEmpty()
  expect(page.url()).not.toBe(first)
})

test("Enter sends, Shift+Enter creates a line, and IME composition does not submit", async ({
  page,
}) => {
  const mock = await mockChat(page)
  await page.goto("/?intent=ask")
  const editor = page.getByRole("textbox", { name: "Your question" })
  await editor.fill(question)
  await editor.dispatchEvent("keydown", { key: "Enter", isComposing: true })
  expect(mock.submissions).toHaveLength(0)
  await editor.press("Shift+Enter")
  await expect(editor).toHaveValue(`${question}\n`)
  await editor.press("Enter")
  await expect.poll(() => mock.submissions.length).toBe(1)
})

test("A fallback keeps the edition caveat and a source can be saved inside chat", async ({
  page,
}) => {
  await mockChat(page, { ...answer, outcome: "validation_failed", blocks: [] })
  await page.goto("/?intent=ask")
  await sendQuestion(page)
  const region = page.getByRole("region", { name: "Answer", exact: true })
  await expect(region).toContainText("Later amendments aren't included yet")
  await region.getByRole("button", { name: "More about this section" }).click()
  await page.getByRole("button", { name: "Save source", exact: true }).click()
  await expect(
    page.getByRole("button", { name: "Remove saved source" }),
  ).toHaveAttribute("aria-pressed", "true")
  await page.reload()
  await expect(region).toContainText("Later amendments aren't included yet")
})

function statuteNoticeSources(): EvidenceItem[] {
  const acja: EvidenceItem = {
    ...evidence,
    evidence_id: "E2",
    canonical_path: "acja-2015.section9",
    citation: "Section 9, ACJA 2015",
    short_citation: "ACJA s.9",
    instrument_slug: "acja-2015",
    instrument_title: "Administration of Criminal Justice Act 2015",
    instrument_short_title: "ACJA 2015",
    instrument_type: "act",
    edition_label: "As enacted, may have been amended.",
    authoritative_text: "Synthetic ACJA provision for notice-display testing.",
    source_title: "Synthetic ACJA fixture",
  }
  const police: EvidenceItem = {
    ...acja,
    evidence_id: "E3",
    canonical_path: "police-act-2020.section49",
    citation: "Section 49, Police Act 2020",
    short_citation: "Police Act s.49",
    instrument_slug: "police-act-2020",
    instrument_title: "Nigeria Police Act 2020",
    instrument_short_title: "Police Act 2020",
    authoritative_text:
      "Synthetic Police Act provision for notice-display testing.",
    source_title: "Synthetic Police Act fixture",
  }
  return [acja, police]
}

test("Chat preserves server coverage and each law's edition notice", async ({
  page,
}) => {
  const [acja, police] = statuteNoticeSources()
  const notice =
    "The published provisions don't seem to answer this directly. This edition includes Constitution, ACJA 2015 and Police Act 2020."
  await mockChat(page, {
    ...answer,
    outcome: "insufficient_evidence",
    blocks: [],
    citation_outcomes: [],
    evidence: [evidence, acja, police],
    notice,
  })
  await page.goto("/?intent=ask")
  await sendQuestion(page)
  const region = page.getByRole("region", { name: "Answer", exact: true })
  await expect(region.getByRole("status")).toHaveText(notice)
  await expect(region).toContainText(
    "ACJA 2015: As enacted, may have been amended.",
  )
  await expect(region).toContainText(
    "Police Act 2020: As enacted, may have been amended.",
  )
  await expect(region).toContainText("Constitution as published in 2004")
  await page.screenshot({
    path: "../output/playwright/statute-phase5-law-notices.png",
    fullPage: true,
  })
})

test("A completed answer displays the server's separate law caveats", async ({
  page,
}) => {
  const notice =
    "Based on the 1999 Constitution as published in 2004. Later amendments aren't included yet.\n\nACJA 2015: As enacted, may have been amended.\n\nPolice Act 2020: As enacted, may have been amended."
  await mockChat(page, {
    ...answer,
    notice,
    evidence: [evidence, ...statuteNoticeSources()],
    blocks: [
      ...answer.blocks,
      {
        text: "Synthetic Act explanation for notice-display testing.",
        evidence_ids: ["E2", "E3"],
        quotation: null,
      },
    ],
  })
  await page.goto("/?intent=ask")
  await sendQuestion(page)
  const region = page.getByRole("region", { name: "Answer", exact: true })
  await expect(region).toContainText(
    "ACJA 2015: As enacted, may have been amended.",
  )
  await expect(region).toContainText(
    "Police Act 2020: As enacted, may have been amended.",
  )
  await expect(region).toContainText("Constitution as published in 2004")
  await region
    .getByRole("button", { name: "Section 9, ACJA 2015", exact: true })
    .click()
  const sources = page.getByRole("complementary", {
    name: "Section details",
    exact: true,
  })
  await expect(sources).toContainText("What ACJA 2015 says")
  await expect(
    sources.getByRole("link", { name: "Open full section" }),
  ).toHaveAttribute(
    "href",
    `/laws/acja-2015/acja-2015.section9?release=${releaseVersion}`,
  )
  await expect(sources).toContainText(
    "ACJA 2015: As enacted, may have been amended.",
  )
})

test("Exported Act answers retain the law, source caveat and canonical URL", async ({
  page,
}) => {
  const acja = statuteNoticeSources()[0]
  await mockChat(page, {
    ...answer,
    evidence: [acja],
    blocks: [
      {
        text: "Synthetic Act answer for export testing.",
        evidence_ids: ["E2"],
        quotation: null,
      },
    ],
  })
  await page.goto("/?intent=ask")
  await sendQuestion(page)
  const region = page.getByRole("region", { name: "Answer", exact: true })
  await expect(
    region.getByRole("button", { name: "Section 9, ACJA 2015", exact: true }),
  ).toHaveText("ACJA s.9")
  const downloading = page.waitForEvent("download")
  await region
    .getByRole("button", { name: "Export answer", exact: true })
    .click()
  const download = await downloading
  const exported = JSON.parse(await readFile((await download.path())!, "utf8"))
  expect(exported.answer.evidence[0].instrument_slug).toBe("acja-2015")
  expect(exported.sources[0]).toContain("ACJA 2015 (as enacted)")
  expect(exported.sources[0]).toContain(
    "ACJA 2015: As enacted, may have been amended.",
  )
  expect(exported.sources[0]).toContain(
    `/laws/acja-2015/acja-2015.section9?release=${releaseVersion}`,
  )
})

const yorubaBlock = "Òfin-Ìpìlẹ̀ dáàbò bo ìpamọ́ nínú ilé àti ìbánisọ̀rọ̀."
const translatedAnswer: ChatAnswer = {
  ...answer,
  question_language: "yo",
  answer_language: "yo",
  translation: {
    language: "yo",
    blocks: [{ text: yorubaBlock, evidence_ids: ["E1"], quotation: null }],
    missing_facts: [],
    follow_up_questions: [],
    model: "test-translator",
    prompt_version: "answer-translation-v2",
    glossary_version: null,
  },
}

test("A translated answer shows the reader's language with an English toggle", async ({
  page,
}) => {
  await mockChat(page, translatedAnswer)
  await page.goto("/?intent=ask")
  await sendQuestion(page)
  const region = page.getByRole("region", { name: "Answer", exact: true })
  await expect(region.getByText(yorubaBlock)).toBeVisible()
  await expect(region.locator('[lang="yo"]')).toContainText(yorubaBlock)
  await expect(region.getByText("Translated from English")).toBeVisible()
  await expect(region.getByText("Beta", { exact: true })).toBeVisible()
  await region.getByRole("button", { name: "Show English" }).click()
  await expect(region.getByText(answer.blocks[0].text)).toBeVisible()
  await expect(region.getByText(yorubaBlock)).toHaveCount(0)
  await expect(
    region.getByRole("button", { name: "Show in Yorùbá" }),
  ).toBeVisible()
})

test("A translation that could not be checked falls back to English with a note", async ({
  page,
}) => {
  await mockChat(page, { ...translatedAnswer, translation: null })
  await page.goto("/?intent=ask")
  await sendQuestion(page)
  const region = page.getByRole("region", { name: "Answer", exact: true })
  await expect(region.getByText(answer.blocks[0].text)).toBeVisible()
  await expect(
    region.getByText(
      "We couldn't translate this answer, so it's shown in English.",
    ),
  ).toBeVisible()
})

test("A non-English interface asks for answers in its language when enabled", async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem(
      "law-padi.preferences.v1",
      JSON.stringify({ language: "yoruba" }),
    ),
  )
  const mock = await mockChat(page, translatedAnswer, {
    answerLanguages: ["en", "yo"],
  })
  await page.goto("/?intent=ask")
  await expect(page.locator("html")).toHaveAttribute("lang", "yo")
  await page.getByRole("textbox", { name: "Ìbéèrè rẹ" }).fill(question)
  await page.getByRole("button", { name: "Fi ìbéèrè ránṣẹ́" }).click()
  await expect.poll(() => mock.submissions.length).toBe(1)
  expect(mock.submissions[0].answer_language).toBe("yo")
})

test("An English interface leaves the answer language to the question", async ({
  page,
}) => {
  const mock = await mockChat(page, answer, { answerLanguages: ["en", "yo"] })
  await page.goto("/?intent=ask")
  await sendQuestion(page)
  await expect.poll(() => mock.submissions.length).toBe(1)
  expect(mock.submissions[0].answer_language).toBeNull()
})
