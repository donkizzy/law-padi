import { defineConfig, devices } from "@playwright/test"
import config from "./playwright.mocked.config"

// Focused layout and language checks in Firefox and WebKit. These specs stub
// their API calls, so like the mocked run this needs no backend. CI runs only
// Chromium; run this by hand (`bun run test:cross-engine`) after changing
// layout, CSS or translated copy.
export default defineConfig({
  ...config,
  testMatch: /(?:production-layout|locale|laws)\.spec\.ts/,
  projects: [
    { name: "firefox-qa", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit-qa", use: { ...devices["Desktop Safari"] } },
  ],
})
