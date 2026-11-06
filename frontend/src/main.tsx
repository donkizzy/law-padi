import { QueryClientProvider } from "@tanstack/react-query"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import {
  AxiosError,
  CanceledError,
  type InternalAxiosRequestConfig,
} from "axios"
import { StrictMode } from "react"
import ReactDOM from "react-dom/client"
import { client } from "./client/client.gen"
import { ThemeProvider } from "./components/theme-provider"
import { Toaster } from "./components/ui/sonner"
import "./index.css"
import { migrateLegacyBookmarks } from "./hooks/useSavedProvisions"
import {
  clearDrafts,
  discardLegacyDrafts,
} from "./hooks/useWorkspacePreferences"
import { stopAccountSync } from "./lib/account-sync"
import { cancelChatRequests } from "./lib/chat-navigation"
import { initI18n } from "./lib/i18n"
import { queryClient } from "./lib/query-client"
import {
  belongsToCurrentSession,
  getAccessToken,
  getSessionOwner,
  getSessionScope,
  getSessionSignal,
  hasSessionHint,
  initSession,
  isSignedIn,
  refreshSession,
  subscribeSession,
} from "./lib/session"
import { routeTree } from "./routeTree.gen"

client.setConfig({
  baseURL: import.meta.env.VITE_API_URL ?? "",
  auth: () => getAccessToken() ?? "",
  withCredentials: true,
})

type SessionRequest = InternalAxiosRequestConfig & {
  _retried?: boolean
  _sessionScope?: number
}

client.instance.interceptors.request.use((config: SessionRequest) => {
  if (!config.url?.includes("/login/")) {
    const authorization = config.headers.get("Authorization")
    if (
      typeof authorization === "string" &&
      authorization.startsWith("Bearer ") &&
      !belongsToCurrentSession(authorization.slice("Bearer ".length))
    )
      throw new CanceledError()
    config._sessionScope ??= getSessionScope()
    const signal = getSessionSignal()
    config.signal =
      config.signal instanceof AbortSignal
        ? AbortSignal.any([config.signal, signal])
        : signal
  }
  return config
})

// An expired access token gets one silent refresh and retry before the
// request fails. Login routes are excluded so a failed refresh can't loop.
client.instance.interceptors.response.use(undefined, async (error) => {
  const config = error?.config as SessionRequest | undefined
  if (
    error instanceof AxiosError &&
    error.response?.status === 401 &&
    config &&
    !config._retried &&
    config._sessionScope === getSessionScope() &&
    isSignedIn()
  ) {
    config._retried = true
    const token = await refreshSession()
    if (token && config._sessionScope === getSessionScope()) {
      config.headers.set("Authorization", `Bearer ${token}`)
      return client.instance.request(config)
    }
  }
  throw error
})

// Public-only server data avoids fetching the same release again at startup.
const initial = document.getElementById("public-corpus-data")
if (initial?.textContent) {
  try {
    const data = JSON.parse(initial.textContent)
    if (data.kind === "provision" && typeof data.path === "string")
      queryClient.setQueryData(
        ["legal", "provision", data.path, data.release],
        data.data,
      )
    if (data.kind === "tree")
      queryClient.setQueryData(
        [
          "legal",
          "tree",
          data.parent ?? undefined,
          data.release,
          data.instrument,
        ],
        data.data,
      )
  } catch {
    /* A failed bootstrap must not prevent the app from loading. */
  }
  initial.remove()
}
const router = createRouter({ routeTree })
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

let scope = getSessionScope()
let owner = getSessionOwner()
let routerMounted = false
subscribeSession(() => {
  if (scope === getSessionScope()) return
  scope = getSessionScope()
  const leavingAccount = owner !== null
  stopAccountSync(owner)
  if (leavingAccount) {
    try {
      clearDrafts()
    } catch {
      // Storage can be disabled by the browser.
    }
  }
  owner = getSessionOwner()
  if (!routerMounted) return
  cancelChatRequests()
  queryClient.removeQueries({
    predicate: ({ queryKey: [key, resource] }) =>
      key !== "chat-capabilities" &&
      key !== "verifyEmail" &&
      (key !== "legal" || resource === "search"),
  })
  queryClient.getMutationCache().clear()
  const location = router.state.location
  if (
    leavingAccount &&
    location.pathname === "/" &&
    (location.search.c || location.search.q || location.search.selected)
  ) {
    void router.navigate({ to: "/", search: {}, replace: true })
    return
  }
  void router.invalidate()
})

// A failed catalogue load falls back to English rather than blocking the app.
try {
  migrateLegacyBookmarks(hasSessionHint())
} catch {
  // Storage can be disabled by the browser.
}
try {
  discardLegacyDrafts()
} catch {
  // Storage can be disabled by the browser.
}
void Promise.allSettled([initSession(), initI18n()]).finally(() => {
  document.querySelectorAll("[data-public-head]").forEach((node) => {
    node.remove()
  })
  routerMounted = true
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <ThemeProvider defaultTheme="light" storageKey="law-padi-theme">
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
          <Toaster richColors closeButton />
        </QueryClientProvider>
      </ThemeProvider>
    </StrictMode>,
  )
})
