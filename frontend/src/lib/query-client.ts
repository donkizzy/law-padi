import { QueryClient } from "@tanstack/react-query"
import { isAxiosError } from "axios"

/** A request the server rejected will be rejected again, so it is not retried. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  const status = isAxiosError(error) ? error.response?.status : undefined
  if (status !== undefined && status >= 400 && status < 500) return false
  return failureCount < 1
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      // Returning to the tab must not repeat a request that costs money (a
      // search embeds the query and may translate it) or flash a loading
      // state. Queries that want a refresh on focus opt in.
      refetchOnWindowFocus: false,
      retry: shouldRetry,
    },
  },
})
