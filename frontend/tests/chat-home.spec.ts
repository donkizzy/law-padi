import { expect, type Page, test } from "@playwright/test"

const conversationId = "11111111-1111-4111-8111-111111111111"
const runId = "22222222-2222-4222-8222-222222222222"
const releaseVersion = "published-historical-test"
const editionLabel = "Historical/source Constitution compilation (LFN 2004)"
const question = "What does Section 37 protect?"
const evidence = {
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
const outcome = {
  reference: "Section 37",
  status: "resolved",
  evidence_ids: ["E1"],
  message: null,
}
const answer = {
  outcome: "answered",
  blocks: [
    {
      text: "The Constitution protects privacy in homes and communications.",
      evidence_ids: ["E1"],
      quotation: null,
    },
  ],
  missing_facts: [],
  citation_outcomes: [outcome],
  evidence: [evidence],
  notice: null,
}
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
  deliveredAnswer = answer,
  options: {
    acceptance?: Promise<void>
    events?: Promise<void>
    failedSubmissions?: number
    historyFailures?: number
    interruptStream?: boolean
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
      const messages = submitted
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
          answer_status: "answered",
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
    await page.goto("/")
    await expect(
      page.getByRole("heading", { name: "Ask about Nigeria's Constitution." }),
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
      `/constitution/${evidence.canonical_path}?release=${releaseVersion}`,
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
  await page.goto("/")
  await page.getByRole("textbox", { name: "Your question" }).fill(question)
  await page.getByRole("button", { name: "Send question" }).click()
  const region = page.getByRole("region", { name: "Answer", exact: true })
  await expect(region.getByRole("status")).toContainText(
    "confident matches the Constitution's text",
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
        text: "Generally, no. The Constitution protects your privacy.",
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
    follow_up_questions: [followUp],
  })
  await page.goto("/")
  await page.getByRole("textbox", { name: "Your question" }).fill(question)
  await page.getByRole("button", { name: "Send question" }).click()
  const region = page.getByRole("region", { name: "Answer", exact: true })
  await expect(region.getByRole("listitem")).toHaveText([
    "your home",
    "your correspondence",
    "your phone conversations",
    "Whether a court order allowed the search",
  ])
  await expect(region).toContainText("What could change this for you")
  await region.getByRole("button", { name: followUp }).click()
  await expect.poll(() => mock.submissions.length).toBe(2)
  expect(mock.submissions[1].question).toBe(followUp)
})

test("Logout removes account conversation data from the next guest view", async ({
  page,
}) => {
  await page.route("**/api/v1/users/me", (route) =>
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
  await page.route("**/api/v1/conversations**", (route) => {
    if (new URL(route.request().url()).pathname.endsWith("/capabilities"))
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
    return route.fulfill({
      json: {
        data: authenticated
          ? [{ ...conversation, title: "Private account conversation" }]
          : [],
        count: authenticated ? 1 : 0,
      },
    })
  })
  await page.goto("/login")
  await page.evaluate(() =>
    localStorage.setItem("access_token", "account-token"),
  )
  await page.goto("/")
  await expect(page.getByText("Private account conversation")).toBeVisible()
  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log Out" }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto("/")
  await expect(page.getByText("Private account conversation")).toHaveCount(0)
  await expect(page.getByText("Your chats will appear here.")).toBeVisible()
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
    await page.goto("/")
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

test("New detaches an active answer without disabling the new editor", async ({
  page,
}) => {
  let releaseEvents!: () => void
  const events = new Promise<void>((resolve) => {
    releaseEvents = resolve
  })
  await mockChat(page, answer, { events })
  await page.goto("/")
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
  await page.goto("/")
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
  await page.goto("/")
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
  await page.goto("/")
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
  await page.goto("/")
  await expect(
    page.getByRole("heading", { name: "Ask about Nigeria's Constitution." }),
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
  await page.goto("/")
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
  await page.goto("/")
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
  await page.goto("/")
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
