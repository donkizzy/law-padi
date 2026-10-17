import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query"
import { AxiosError } from "axios"
import { endSession, isSignedIn } from "./session"

const handleApiError = (error: Error) => {
  if (
    error instanceof AxiosError &&
    error.response?.status === 401 &&
    isSignedIn()
  )
    endSession()
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleApiError }),
  mutationCache: new MutationCache({ onError: handleApiError }),
})
