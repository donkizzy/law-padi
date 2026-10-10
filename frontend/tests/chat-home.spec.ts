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
      text: "The stored wording protects privacy in homes and communications.",
      evidence_ids: ["E1"],
      quotation: null,
    },
  ],
  missing_facts: [],
  citation_outcomes: [outcome],
  evidence: [evidence],
  notice: "This is an AI explanation of a historical source edition.",
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

async function mockChat(page: Page, deliveredAnswer = answer) {
  let created = false
  let submitted = false
  let completed = false
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
    if (path.endsWith(`/conversations/${conversationId}/events`)) {
      expect(new URL(request.url()).searchParams.get("run_id")).toBe(runId)
      completed = true
      const events = [
        {
          id: 1,
          event: "retrieval.complete",
          data: { evidence: [evidence], citation_outcomes: [outcome] },
        },
        { id: 2, event: "answer.complete", data: { answer: deliveredAnswer } },
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
      submitted = true
      submissions.push(request.postDataJSON())
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
      return route.fulfill({ status: 201, json: conversation })
    }
    if (path.endsWith("/conversations") && request.method() === "GET")
      return route.fulfill({
        json: {
          data: created ? [conversation] : [],
          count: created ? 1 : 0,
        },
      })
    return route.fulfill({ status: 404, json: { detail: "Not found" } })
  })
  return { submissions }
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
    await page
      .getByRole("textbox", { name: "Your constitutional question" })
      .fill(question)
    await page.getByRole("button", { name: "Send question" }).click()
    await expect(
      page.getByRole("region", { name: "AI explanation" }),
    ).toContainText("protects privacy")
    const explanation = page.getByRole("region", { name: "AI explanation" })
    const answerTop = await explanation
      .getByText(/stored wording protects privacy/)
      .evaluate((element) => element.getBoundingClientRect().top)
    const evidenceTop = await explanation
      .getByRole("heading", { name: "Stored source wording" })
      .evaluate((element) => element.getBoundingClientRect().top)
    expect(answerTop).toBeLessThan(evidenceTop)
    expect(mock.submissions).toHaveLength(1)
    expect(mock.submissions[0].idempotency_key).toBeTruthy()

    await page
      .getByRole("region", { name: "AI explanation" })
      .getByRole("button", { name: "Section 37", exact: true })
      .click()
    if (mobile)
      await expect(
        page.getByRole("dialog", { name: "Legal source inspector" }),
      ).toContainText(evidence.authoritative_text)
    else
      await expect(
        page.getByRole("complementary", { name: "Legal source inspector" }),
      ).toContainText(evidence.authoritative_text)
    await expect(
      page.getByRole("link", { name: "Open provision" }),
    ).toHaveAttribute(
      "href",
      `/constitution/${evidence.canonical_path}?release=${releaseVersion}`,
    )
    await page.getByRole("button", { name: "Explain this identity" }).click()
    await expect.poll(() => mock.submissions.length).toBe(2)
    expect(mock.submissions[1]).toMatchObject({
      question: "Section 37",
      selected_provision_version_id: evidence.provision_version_id,
    })
    await page.reload()
    await expect(
      page.getByRole("region", { name: "AI explanation" }),
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
    notice:
      "The generated explanation could not be validated. The source wording is available.",
  })
  await page.goto("/")
  await page
    .getByRole("textbox", { name: "Your constitutional question" })
    .fill(question)
  await page.getByRole("button", { name: "Send question" }).click()
  const region = page.getByRole("region", { name: "AI explanation" })
  await expect(region).toContainText(
    "Best published source wording · Section 131",
  )
  await expect(region).toContainText("citizen of Nigeria by birth")
  await expect(region).toContainText("could not be validated")
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
