import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"

import {
  type Body_login_login_access_token as AccessToken,
  LoginService,
  type UserPublic,
  type UserRegister,
  UsersService,
} from "@/client"
import { stopAccountSync } from "@/lib/account-sync"
import { safeRedirect } from "@/lib/redirect"
import {
  endSession,
  isSignedIn,
  startSession,
  useSessionStatus,
} from "@/lib/session"
import { handleError } from "@/utils"
import useCustomToast from "./useCustomToast"
import { clearDrafts } from "./useWorkspacePreferences"

const isLoggedIn = isSignedIn

type UseAuthOptions = {
  /** Where to go after signing in, from the page's `?redirect=`. */
  redirect?: string
}

const useAuth = ({ redirect }: UseAuthOptions = {}) => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const status = useSessionStatus()

  const { data: user } = useQuery<UserPublic | null, Error>({
    queryKey: ["currentUser"],
    queryFn: async () => (await UsersService.readUserMe()).data,
    enabled: status === "signed-in",
  })

  const signUpMutation = useMutation({
    mutationFn: (data: UserRegister) =>
      UsersService.registerUser({ body: data }),
    onSuccess: () => {
      navigate({
        to: "/login",
        search: { redirect: safeRedirect(redirect), notice: "check-email" },
      })
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const login = async (data: AccessToken) => {
    const response = await LoginService.loginAccessToken({
      body: data,
    })
    queryClient.removeQueries()
    startSession(response.data.access_token)
  }

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: () => {
      const target = safeRedirect(redirect)
      if (target) navigate({ href: target })
      else navigate({ to: "/" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const logout = async () => {
    try {
      await LoginService.logout()
    } catch {
      /* Sign out locally even if the server can't be reached. */
    }
    endSession()
    stopAccountSync({ clearLocal: true })
    try {
      clearDrafts()
    } catch {
      /* Signing out must work when browser storage is blocked. */
    }
    queryClient.clear()
    navigate({ to: "/login" })
  }

  return {
    signUpMutation,
    loginMutation,
    logout,
    user,
  }
}

export { isLoggedIn }
export default useAuth
