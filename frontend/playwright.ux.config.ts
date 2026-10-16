import { defineConfig, devices } from "@playwright/test"

// Every API request in these files is mocked: no accounts, corpus writes or model calls.
export default defineConfig({
  testDir: "./tests",
  testMatch: [
    "chat-home.spec.ts",
    "legal-home.spec.ts",
    "user-settings.spec.ts",
  ],
  fullyParallel: true,
  workers: 3,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:5173",
    ...devices["Desktop Chrome"],
    storageState: { cookies: [], origins: [] },
    trace: "retain-on-failure",
  },
  webServer: {
    command: "bun run dev -- --host 127.0.0.1",
    url: "http://localhost:5173",
    reuseExistingServer: true,
  },
})
