import { defineConfig, devices } from "@playwright/test"
import { backendSpecs } from "./tests/backend-specs.ts"

// Every spec except the backend ones stubs its API calls, so this runs against
// the Vite dev server alone: no database, mail catcher, accounts or model calls.
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173"

export default defineConfig({
  testDir: "./tests",
  testIgnore: backendSpecs,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  workers: 3,
  retries: 0,
  // Named blob, so merging it with the backend job's report cannot overwrite either.
  reporter: process.env.CI
    ? [["list"], ["blob", { fileName: "report-mocked.zip" }]]
    : "list",
  use: {
    baseURL,
    ...devices["Desktop Chrome"],
    storageState: { cookies: [], origins: [] },
    trace: "retain-on-failure",
  },
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: "bun run dev -- --host 127.0.0.1",
        url: baseURL,
        reuseExistingServer: !process.env.CI,
      },
})
