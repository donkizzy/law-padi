import type { Page } from "@playwright/test"
import type {
  ChatCapabilities,
  LegalInstrumentPublic,
  LegalReleasePublic,
} from "../../src/client"
import { chatCapabilities, conversationList } from "./chat.ts"
import { currentRelease, legalInstruments } from "./legal.ts"

// The requests every page makes on load: chat capabilities and history, the
// current release, and the instrument list. Specs install these, then layer
// the endpoints they exercise on top (the last registered route wins).

/** Answer the capability probe and report an empty chat history. */
export async function mockChatShell(
  page: Page,
  capabilities: Partial<ChatCapabilities> = {},
) {
  const body = chatCapabilities(capabilities)
  await page.route("**/api/v1/conversations**", (route) =>
    route.fulfill({
      json: new URL(route.request().url()).pathname.endsWith("/capabilities")
        ? body
        : conversationList(),
    }),
  )
}

export async function mockCurrentRelease(
  page: Page,
  overrides: Partial<LegalReleasePublic> = {},
) {
  const body = currentRelease(overrides)
  await page.route("**/api/v1/legal/releases/current", (route) =>
    route.fulfill({ json: body }),
  )
}

export async function mockInstruments(
  page: Page,
  instruments: LegalInstrumentPublic[] = [],
  releaseVersion?: string,
) {
  const body = legalInstruments(instruments, releaseVersion)
  await page.route("**/api/v1/legal/instruments**", (route) =>
    route.fulfill({ json: body }),
  )
}
