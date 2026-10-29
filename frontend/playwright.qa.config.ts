import { defineConfig, devices } from "@playwright/test"
import config from "./playwright.config"

// Focused, mocked cross-engine checks; no live sign-in or provider calls.
export default defineConfig({
  ...config,
  testMatch: /(?:production-layout|locale|laws)\.spec\.ts/,
  projects: [
    { name: "firefox-qa", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit-qa", use: { ...devices["Desktop Safari"] } },
  ],
})
