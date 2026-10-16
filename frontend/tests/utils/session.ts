import type { Page } from "@playwright/test"

export const SESSION_HINT_KEY = "constitution_session"

/**
 * Fake a signed-in browser without the real API: the page finds the session
 * hint, its refresh call returns `accessToken`, and signing out ends it.
 */
export async function mockSignedIn(page: Page, accessToken = "account-token") {
  let signedIn = true
  await page.addInitScript(
    (key) => localStorage.setItem(key, "1"),
    SESSION_HINT_KEY,
  )
  await page.route("**/api/v1/login/refresh", (route) =>
    signedIn
      ? route.fulfill({
          json: { access_token: accessToken, token_type: "bearer" },
        })
      : route.fulfill({ status: 401, json: { detail: "Session expired" } }),
  )
  await page.route("**/api/v1/login/logout", (route) => {
    signedIn = false
    return route.fulfill({ json: { message: "Signed out" } })
  })
}
