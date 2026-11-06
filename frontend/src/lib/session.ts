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
let owner: string | null = null
let scope = 0
let requests = new AbortController()
let refreshTimer: ReturnType<typeof setTimeout> | undefined
let inFlight: Promise<string | null> | null = null
const listeners = new Set<() => void>()

const channel =
  typeof BroadcastChannel === "undefined"
    ? null
    : new BroadcastChannel(CHANNEL_NAME)

channel?.addEventListener("message", (event) => {
  if (event.data === "signed-out") setSession(null, { broadcast: false })
  if (
    event.data?.type === "signed-in" &&
    typeof event.data.owner === "string" &&
    event.data.owner !== owner
  ) {
    setSession(null, { broadcast: false, keepHint: true })
    void refreshSession()
  }
})

function storage(action: (store: Storage) => void) {
  try {
    action(localStorage)
  } catch {
    /* Sessions must work when browser storage is blocked. */
  }
}

function tokenClaims(token: string): { sub?: string; exp?: number } {
  try {
    return (
      JSON.parse(
        atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
      ) ?? {}
    )
  } catch {
    return {}
  }
}

function scheduleRefresh(token: string | null) {
  clearTimeout(refreshTimer)
  const expiry = token ? tokenClaims(token).exp : undefined
  if (typeof expiry !== "number") return
  const delay = Math.max(expiry * 1000 - Date.now() - REFRESH_EARLY_MS, 5_000)
  refreshTimer = setTimeout(() => void refreshSession(), delay)
}

function setSession(
  token: string | null,
  { broadcast = true, keepHint = false } = {},
) {
  const wasSignedIn = status === "signed-in"
  const subject = token ? tokenClaims(token).sub : undefined
  const nextOwner = token
    ? typeof subject === "string" && subject
      ? subject
      : "signed-in"
    : null
  if (nextOwner !== owner || !token) {
    scope += 1
    requests.abort()
    requests = new AbortController()
    inFlight = null
  }
  owner = nextOwner
  accessToken = token
  status = token ? "signed-in" : "guest"
  scheduleRefresh(token)
  if (!keepHint)
    storage((store) =>
      token ? store.setItem(HINT_KEY, "1") : store.removeItem(HINT_KEY),
    )
  if (broadcast && wasSignedIn && !token) channel?.postMessage("signed-out")
  for (const listener of listeners) listener()
}

export const getAccessToken = () => accessToken
export const getSessionStatus = () => status
export const isSignedIn = () => status === "signed-in"
export const getSessionOwner = () => owner
export const getSessionScope = () => scope
export const getSessionSignal = () => requests.signal
export const hasSessionHint = () => Boolean(localStorage.getItem(HINT_KEY))

export function belongsToCurrentSession(token: string): boolean {
  if (!accessToken) return false
  const subject = tokenClaims(token).sub
  return token === accessToken || (Boolean(subject) && subject === owner)
}

export function subscribeSession(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function useSessionStatus(): SessionStatus {
  return useSyncExternalStore(subscribeSession, getSessionStatus)
}

export function useSessionScope(): number {
  return useSyncExternalStore(subscribeSession, getSessionScope)
}

/** Call after a successful sign-in with the access token it returned. */
export function startSession(token: string) {
  setSession(token)
  channel?.postMessage({ type: "signed-in", owner })
}

/** Forget the in-memory token. The caller revokes the cookie server-side. */
export const endSession = () => setSession(null)

export async function withSessionLock<T>(task: () => Promise<T>): Promise<T> {
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
  if (inFlight) return inFlight
  const started = scope
  const refresh = withSessionLock(async () => {
    if (scope !== started) return null
    try {
      const response = await LoginService.refreshAccessToken({
        throwOnError: true,
      })
      if (scope !== started) return null
      setSession(response.data.access_token)
      return response.data.access_token
    } catch (error) {
      const unauthorized =
        (error as { response?: { status?: number } }).response?.status === 401
      if (scope === started && (unauthorized || status !== "signed-in")) {
        setSession(null, { keepHint: !unauthorized })
      }
      return null
    }
  }).finally(() => {
    if (inFlight === refresh) inFlight = null
  })
  inFlight = refresh
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
  storage(() => {
    hinted = hasSessionHint()
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
