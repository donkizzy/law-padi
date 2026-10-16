import { z } from "zod"

const AUTH_PAGES = ["/login", "/signup", "/recover-password", "/reset-password"]

/**
 * A `?redirect=` value is only followed when it is a path inside this app.
 * Anything else (another site, `//host`, `/\host`, an auth page) is dropped,
 * so sign-in links can't be used to bounce people to a lookalike site.
 */
export function safeRedirect(value: unknown): string | undefined {
  if (typeof value !== "string" || value.length > 2048) return undefined
  if (!value.startsWith("/")) return undefined
  // Resolve the way a browser would (it strips tabs and newlines and treats
  // "\\" like "/"), then insist the result stays on this origin.
  const base = "https://constitution.invalid"
  let url: URL
  try {
    url = new URL(value, base)
  } catch {
    return undefined
  }
  if (url.origin !== base || AUTH_PAGES.includes(url.pathname)) return undefined
  return `${url.pathname}${url.search}${url.hash}`
}

export const redirectSearchSchema = z.object({
  redirect: z.string().max(2048).optional().catch(undefined),
})
