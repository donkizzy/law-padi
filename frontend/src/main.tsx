import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import { AxiosError, type InternalAxiosRequestConfig } from "axios"
import { StrictMode } from "react"
import ReactDOM from "react-dom/client"
import { client } from "./client/client.gen"
import { ThemeProvider } from "./components/theme-provider"
import { Toaster } from "./components/ui/sonner"
import "./index.css"
import { stopAccountSync } from "./lib/account-sync"
import {
  endSession,
  getAccessToken,
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

// An expired access token gets one silent refresh and retry before the
// request fails. Login routes are excluded so a failed refresh can't loop.
client.instance.interceptors.response.use(undefined, async (error) => {
  const config = error?.config as
    | (InternalAxiosRequestConfig & { _retried?: boolean })
    | undefined
  if (
    error instanceof AxiosError &&
    error.response?.status === 401 &&
    config &&
    !config._retried &&
    !config.url?.includes("/login/") &&
    isSignedIn()
  ) {
    config._retried = true
    const token = await refreshSession()
    if (token) {
      config.headers.set("Authorization", `Bearer ${token}`)
      return client.instance.request(config)
    }
  }
  throw error
})

const handleApiError = (error: Error) => {
  // 401 here means the refresh failed too: continue as a guest. Route guards
  // re-run below and send protected pages to /login. 403 is a permission
  // answer, not a sign-out.
  if (
    error instanceof AxiosError &&
    error.response?.status === 401 &&
    isSignedIn()
  ) {
    endSession()
  }
}
const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: handleApiError,
  }),
  mutationCache: new MutationCache({
    onError: handleApiError,
  }),
})

const router = createRouter({ routeTree })
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

let signedIn = isSignedIn()
subscribeSession(() => {
  if (signedIn === isSignedIn()) return
  signedIn = isSignedIn()
  // Expired or signed out in another tab: stop sending changes to the account.
  if (!signedIn) stopAccountSync({ clearLocal: false })
  queryClient.removeQueries({ queryKey: ["currentUser"] })
  void router.invalidate()
})

void initSession().finally(() => {
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
