import { expect, type Page, test } from "@playwright/test"
import { firstSuperuser, firstSuperuserPassword } from "./config.ts"
import { randomPassword } from "./utils/random.ts"
import { SESSION_HINT_KEY } from "./utils/session.ts"

test.use({ storageState: { cookies: [], origins: [] } })

const fillForm = async (page: Page, email: string, password: string) => {
  await page.getByTestId("email-input").fill(email)
  await page.getByTestId("password-input").fill(password)
}

const verifyInput = async (page: Page, testId: string) => {
  const input = page.getByTestId(testId)
  await expect(input).toBeVisible()
  await expect(input).toHaveText("")
  await expect(input).toBeEditable()
}

test("Inputs are visible, empty and editable", async ({ page }) => {
  await page.goto("/login")

  await verifyInput(page, "email-input")
  await verifyInput(page, "password-input")
})

test("Log In button is visible", async ({ page }) => {
  await page.goto("/login")

  await expect(page.getByRole("button", { name: "Log In" })).toBeVisible()
})

test("Forgot Password link is visible", async ({ page }) => {
  await page.goto("/login")

  await expect(
    page.getByRole("link", { name: "Forgot your password?" }),
  ).toBeVisible()
})

test("Log in with valid email and password ", async ({ page }) => {
  await page.goto("/login")

  await fillForm(page, firstSuperuser, firstSuperuserPassword)
  await page.getByRole("button", { name: "Log In" }).click()

  await page.waitForURL("/")

  await expect(page.getByTestId("user-menu")).toBeVisible()
})

test("Log in with invalid email", async ({ page }) => {
  await page.goto("/login")

  await fillForm(page, "invalidemail", firstSuperuserPassword)
  await page.getByRole("button", { name: "Log In" }).click()

  await expect(page.getByText("Invalid email address")).toBeVisible()
})

test("Log in with invalid password", async ({ page }) => {
  const password = randomPassword()

  await page.goto("/login")
  await fillForm(page, firstSuperuser, password)
  await page.getByRole("button", { name: "Log In" }).click()

  await expect(page.getByText("Incorrect email or password")).toBeVisible()
})

test("Successful log out", async ({ page }) => {
  await page.goto("/login")

  await fillForm(page, firstSuperuser, firstSuperuserPassword)
  await page.getByRole("button", { name: "Log In" }).click()

  await page.waitForURL("/")

  await expect(page.getByTestId("user-menu")).toBeVisible()

  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log Out" }).click()
  await page.waitForURL("/login")
})

test("Logged-out user cannot access protected routes", async ({ page }) => {
  await page.goto("/login")

  await fillForm(page, firstSuperuser, firstSuperuserPassword)
  await page.getByRole("button", { name: "Log In" }).click()

  await page.waitForURL("/")

  await expect(page.getByTestId("user-menu")).toBeVisible()

  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log Out" }).click()
  await page.waitForURL("/login")

  await page.goto("/admin")
  await expect(page).toHaveURL(/\/login\?redirect=%2Fadmin$/)
})

test("An expired session falls back to browsing as a guest", async ({
  page,
}) => {
  // The hint says this browser signed in before, but there is no live
  // refresh cookie, so the refresh is refused.
  await page.addInitScript(
    (key) => localStorage.setItem(key, "1"),
    SESSION_HINT_KEY,
  )
  await page.goto("/settings")
  await expect(page.getByText("You're browsing as a guest.")).toBeVisible()
  expect(
    await page.evaluate((key) => localStorage.getItem(key), SESSION_HINT_KEY),
  ).toBeNull()
})

test("Signing in keeps the access token out of browser storage", async ({
  page,
}) => {
  await page.goto("/login")
  await fillForm(page, firstSuperuser, firstSuperuserPassword)
  await page.getByRole("button", { name: "Log In" }).click()
  await page.waitForURL("/")
  const stored = await page.evaluate(() => JSON.stringify(localStorage))
  expect(stored).not.toContain("eyJ")
  const cookies = await page.context().cookies()
  const session = cookies.find(({ name }) => name === "constitution_session")
  expect(session?.httpOnly).toBe(true)

  // Reloading restores the session from the cookie.
  await page.reload()
  await expect(page.getByText("You're browsing as a guest.")).toHaveCount(0)
})
