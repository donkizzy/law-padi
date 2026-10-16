import type { Page } from "@playwright/test"

export async function signUpNewUser(
  page: Page,
  name: string,
  email: string,
  password: string,
) {
  await page.goto("/signup")

  await page.getByTestId("full-name-input").fill(name)
  await page.getByTestId("email-input").fill(email)
  await page.getByTestId("password-input").fill(password)
  await page.getByTestId("confirm-password-input").fill(password)
  await page.getByRole("button", { name: "Sign Up" }).click()
  // Wait for sign-up to finish (it sends an email first) before moving on,
  // or the navigation can cancel the request.
  await page.waitForURL(/\/login\?notice=check-email$/)
}

export async function logInUser(page: Page, email: string, password: string) {
  await page.goto("/login")

  await page.getByTestId("email-input").fill(email)
  await page.getByTestId("password-input").fill(password)
  await page.getByRole("button", { name: "Log In" }).click()
  await page.waitForURL("/")
}

export async function logOutUser(page: Page) {
  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log Out" }).click()
  await page.goto("/login")
}
