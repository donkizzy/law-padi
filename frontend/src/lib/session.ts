import { useSyncExternalStore } from "react"

import { LoginService } from "@/client"

/**
 * Browser session state.
 *
 * The access token lives only in memory. A rotating HttpOnly refresh cookie,
 * which scripts cannot read, renews it on page load, shortly before it expires,
 * and when the API answers 401.
 */
export type SessionStatus = "unknown" | "guest" | "signed-in"

// Not a secret: only says "this browser signed in before, so try to refresh".
// It saves guests a refresh request on every page load.
const HINT_KEY = "constitution_session"
const LEGACY_TOKEN_KEY = "access_token"
const LOCK_NAME = "constitution-session-refresh"
const CHANNEL_NAME = "constitution-session"
const BOOT_TIMEOUT_MS = 3000
const REFRESH_EARLY_MS = 60_000

let accessToken: string | null = null
let status: SessionStatus = "unknown"
let refreshTimer: ReturnType<typeof setTimeout> | undefined
let inFlight: Promise<string | null> | null = null
const listeners = new Set<() => void>()

const channel =
  typeof BroadcastChannel === "undefined"
    ? null
    : new BroadcastChannel(CHANNEL_NAME)

channel?.addEventListener("message", (event) => {
  // Another tab signed out: drop our copy of the token too.
  if (event.data === "signed-out") setSession(null, { broadcast: false })
})

function storage(action: (store: Storage) => void) {
  try {
    action(localStorage)
  } catch {
    /* Sessions must work when browser storage is blocked. */
  }
}

function tokenExpiry(token: string): number | null {
  try {
    const payload = JSON.parse(
      atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
    ) as { exp?: number }
    return typeof payload.exp === "number" ? payload.exp * 1000 : null
  } catch {
    return null
  }
}

function scheduleRefresh(token: string | null) {
  clearTimeout(refreshTimer)
  const expiry = token ? tokenExpiry(token) : null
  if (expiry === null) return
  const delay = Math.max(expiry - Date.now() - REFRESH_EARLY_MS, 5_000)
  refreshTimer = setTimeout(() => void refreshSession(), delay)
}

function setSession(token: string | null, { broadcast = true } = {}) {
  const wasSignedIn = status === "signed-in"
  accessToken = token
  status = token ? "signed-in" : "guest"
  scheduleRefresh(token)
  storage((store) =>
    token ? store.setItem(HINT_KEY, "1") : store.removeItem(HINT_KEY),
  )
  if (broadcast && wasSignedIn && !token) channel?.postMessage("signed-out")
  for (const listener of listeners) listener()
}

export const getAccessToken = () => accessToken
export const getSessionStatus = () => status
export const isSignedIn = () => status === "signed-in"

export function subscribeSession(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function useSessionStatus(): SessionStatus {
  return useSyncExternalStore(subscribeSession, getSessionStatus)
}

/** Call after a successful sign-in with the access token it returned. */
export const startSession = (token: string) => setSession(token)

/** Forget the in-memory token. The caller revokes the cookie server-side. */
export const endSession = () => setSession(null)

async function withRefreshLock<T>(task: () => Promise<T>): Promise<T> {
  // Serialise refreshes across tabs so they don't present the same cookie
  // twice; the second tab then sends the cookie the first one received.
  if (typeof navigator !== "undefined" && navigator.locks) {
    return navigator.locks.request(LOCK_NAME, task)
  }
  return task()
}

/**
 * Exchange the refresh cookie for a new access token. Concurrent callers share
 * one request. Resolves to the new token, or null when there is no session.
 */
export function refreshSession(): Promise<string | null> {
  inFlight ??= withRefreshLock(async () => {
    try {
      const response = await LoginService.refreshAccessToken({
        throwOnError: true,
      })
      setSession(response.data.access_token)
      return response.data.access_token
    } catch (error) {
      const unauthorized =
        (error as { response?: { status?: number } }).response?.status === 401
      if (unauthorized || status !== "signed-in") {
        // A network failure leaves the hint in place so the next load retries.
        accessToken = null
        status = "guest"
        clearTimeout(refreshTimer)
        if (unauthorized) storage((store) => store.removeItem(HINT_KEY))
        for (const listener of listeners) listener()
      }
      return null
    }
  }).finally(() => {
    inFlight = null
  })
  return inFlight
}

/**
 * Resolve the session before the router first runs, so route guards and the
 * landing redirect see the right state. Gives up waiting after a few seconds
 * (a cold API start) and lets the refresh finish in the background.
 */
export async function initSession(): Promise<void> {
  // Tokens from before cookie sessions were readable by any script. Drop them;
  // those visitors sign in once more.
  storage((store) => store.removeItem(LEGACY_TOKEN_KEY))
  let hinted = false
  storage((store) => {
    hinted = store.getItem(HINT_KEY) !== null
  })
  if (!hinted) {
    setSession(null, { broadcast: false })
    return
  }
  await Promise.race([
    refreshSession(),
    new Promise((resolve) => setTimeout(resolve, BOOT_TIMEOUT_MS)),
  ])
}
