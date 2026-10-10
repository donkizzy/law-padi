import { expect, test as setup } from "@playwright/test"
import { firstSuperuser, firstSuperuserPassword } from "./config.ts"

const authFile = "playwright/.auth/user.json"

setup("authenticate", async ({ page }) => {
  const requests: string[] = []
  const failures: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/api/"))
      requests.push(`${request.method()} ${request.url()}`)
  })
  page.on("requestfailed", (request) => {
    if (request.url().includes("/api/"))
      failures.push(
        `${request.url()}: ${request.failure()?.errorText ?? "unknown"}`,
      )
  })
  await page.goto("/login")
  await page.getByTestId("email-input").fill(firstSuperuser)
  await page.getByTestId("password-input").fill(firstSuperuserPassword)
  const loginResponse = page.waitForResponse(
    (response) => response.url().includes("/api/v1/login/access-token"),
    { timeout: 30000 },
  )
  await page.getByRole("button", { name: "Log In" }).click()
  const response = await loginResponse.catch(() => null)
  if (!response)
    throw new Error(
      `No login response. Requests: ${requests.join(", ")}. Failures: ${failures.join(", ")}`,
    )
  expect(response.status()).toBe(200)
  await expect(page).toHaveURL("/")
  await page.context().storageState({ path: authFile })
})
