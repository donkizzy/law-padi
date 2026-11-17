import { expect, type Page, type Route, test } from "@playwright/test"
import type { CitationOutcome, EvidenceItem } from "../src/client"
import { mockAdminApi } from "./admin/mockAdminApi.ts"
import {
  chatAnswer,
  chatCapabilities,
  conversationDetail,
  conversationList,
  conversationPublic,
  eventStreamBody,
  messagePublic,
} from "./fixtures/chat.ts"
import { mockCurrentRelease, mockInstruments } from "./fixtures/shell.ts"

// The rendered markup of the admin tabs and the chat page, kept as text
// snapshots. Restructuring those screens into smaller modules must leave every
// snapshot unchanged; a change in markup has to be deliberate and reviewed.

test.use({
  storageState: { cookies: [], origins: [] },
  locale: "en-US",
  timezoneId: "UTC",
  viewport: { width: 1440, height: 1000 },
})

test.beforeEach(async ({ page }, testInfo) => {
  // Markup does not depend on the operating system, so one file serves all.
  testInfo.snapshotSuffix = ""
  await page.clock.install({ time: new Date("2026-11-01T10:00:00Z") })
  await page.emulateMedia({ reducedMotion: "reduce" })
})

/** The body's markup, once it has stopped changing, with volatile values replaced. */
async function stableMarkup(page: Page): Promise<string> {
  const read = () =>
    page.evaluate(() => {
      const body = document.body.cloneNode(true) as HTMLElement
      for (const script of body.querySelectorAll("script")) script.remove()
      return body.innerHTML
    })
  let previous = await read()
  for (let attempt = 0; attempt < 40; attempt += 1) {
    await page.waitForTimeout(250)
    const current = await read()
    if (current === previous) return normalise(current)
    previous = current
  }
  throw new Error("The page kept changing; no stable markup to compare.")
}

function normalise(markup: string): string {
  const ids = new Map<string, string>()
  return (
    markup
      // React's useId and Radix ids depend on render order across the whole tree.
      .replace(/_r_[0-9a-z]+_|«[^»]+»|:r[0-9a-z]+:/g, (id) => {
        if (!ids.has(id)) ids.set(id, `id-${ids.size + 1}`)
        return ids.get(id) as string
      })
      .replace(/blob:[^"')\s]+/g, "blob:url")
      // The admin fixtures stamp records with the wall-clock time.
      .replace(/\b[A-Z][a-z]{2} \d{1,2}, \d{2}:\d{2} [AP]M\b/g, "Mon D, HH:MM")
      // Elapsed seconds on the loading indicator.
      .replace(/>\d+s</g, ">Ns<")
      .replace(/></g, ">\n<")
  )
}

test.describe("admin", () => {
  for (const tab of [
    "Ingestion runs",
    "Page boundaries",
    "Review queue",
    "Corpus releases",
    "Benchmarks",
  ]) {
    test(`${tab} tab markup`, async ({ page }) => {
      await mockAdminApi(page)
      await page.goto("/admin")
      await page.getByRole("tab", { name: tab }).click()
      await expect(page.getByRole("tab", { name: tab })).toHaveAttribute(
        "aria-selected",
        "true",
      )
      expect(await stableMarkup(page)).toMatchSnapshot(
        `admin-${tab.toLowerCase().replace(/ /g, "-")}.txt`,
      )
    })
  }

  test("Upload dialog markup", async ({ page }) => {
    await mockAdminApi(page)
    await page.goto("/admin")
    await page.getByRole("button", { name: "Upload source" }).click()
    await expect(page.getByRole("dialog")).toBeVisible()
    expect(await stableMarkup(page)).toMatchSnapshot("admin-upload-dialog.txt")
  })
})

const conversationId = "11111111-1111-4111-8111-111111111111"
const runId = "22222222-2222-4222-8222-222222222222"
const releaseVersion = "published-historical-test"
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
  edition_label: "Historical/source Constitution compilation (LFN 2004)",
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
    {
      text: "- Homes\n- Correspondence\n- Telephone conversations",
      evidence_ids: ["E1"],
      quotation: null,
    },
  ],
  missing_facts: ["Whether a court order was obtained."],
  follow_up_questions: ["Can the police search my phone?"],
  citation_outcomes: [outcome],
  evidence: [evidence],
})
const conversation = conversationPublic({
  id: conversationId,
  release_version: releaseVersion,
})
const userMessage = messagePublic({ content: "What does Section 37 protect?" })

type ChatState = "complete" | "pending" | "interrupted"

async function mockChatPage(page: Page, state?: ChatState) {
  await mockCurrentRelease(page)
  await mockInstruments(page)
  await page.route("**/api/v1/legal/search", (route) =>
    route.fulfill({ status: 404, json: { detail: "Not found" } }),
  )
  const held: Route[] = []
  await page.route("**/api/v1/conversations**", (route) => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith("/capabilities"))
      return route.fulfill({ json: chatCapabilities() })
    if (path.endsWith(`/conversations/${conversationId}/events`)) {
      if (state === "pending") {
        held.push(route)
        return
      }
      return route.fulfill({
        contentType: "text/event-stream",
        body: eventStreamBody([
          {
            id: 1,
            event: "retrieval.complete",
            data: {
              evidence: [evidence],
              citation_outcomes: [outcome],
              retrieval_mode: "exact",
              message: null,
            },
          },
        ]),
      })
    }
    if (path.endsWith(`/conversations/${conversationId}`)) {
      const messages = [userMessage]
      if (state === "complete")
        messages.push(
          messagePublic({
            id: "88888888-8888-4888-8888-888888888888",
            role: "assistant",
            content: "",
            answer_status: "completed",
            answer_content: answer,
            evidence_snapshot: [evidence],
            created_at: "2026-10-08T08:00:02Z",
          }),
        )
      return route.fulfill({
        json: conversationDetail({
          ...conversation,
          messages,
          active_run_id: state === "complete" ? null : runId,
        }),
      })
    }
    return route.fulfill({
      json: conversationList(state ? [conversation] : []),
    })
  })
  return held
}

test.describe("chat", () => {
  test("New chat markup", async ({ page }) => {
    await mockChatPage(page)
    await page.goto("/?intent=ask")
    await expect(
      page.getByRole("textbox", { name: "Your question" }),
    ).toBeVisible()
    expect(await stableMarkup(page)).toMatchSnapshot("chat-new.txt")
  })

  test("Completed answer markup", async ({ page }) => {
    await mockChatPage(page, "complete")
    await page.goto(`/?c=${conversationId}`)
    await expect(
      page.getByRole("region", { name: "Answer", exact: true }),
    ).toContainText("protects privacy")
    expect(await stableMarkup(page)).toMatchSnapshot("chat-answer.txt")
  })

  test("Answer in progress markup", async ({ page }) => {
    const held = await mockChatPage(page, "pending")
    await page.goto(`/?c=${conversationId}`)
    await expect(
      page.getByRole("region", { name: "Answer in progress" }),
    ).toBeVisible()
    // Hold the loading phrase still while the markup is read.
    const pageNow = await page.evaluate(() => Date.now())
    await page.clock.pauseAt(pageNow + 500)
    expect(await stableMarkup(page)).toMatchSnapshot("chat-pending.txt")
    for (const route of held) await route.abort()
  })

  test("Interrupted stream markup", async ({ page }) => {
    await mockChatPage(page, "interrupted")
    await page.goto(`/?c=${conversationId}`)
    await expect(
      page.getByRole("region", { name: "Answer in progress" }),
    ).toBeVisible()
    expect(await stableMarkup(page)).toMatchSnapshot("chat-interrupted.txt")
  })
})
