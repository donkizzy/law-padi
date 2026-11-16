import { useMutation, useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"

import {
  type Body_login_login_access_token as AccessToken,
  LoginService,
  type UserPublic,
  type UserRegister,
  UsersService,
} from "@/client"
import { safeRedirect } from "@/lib/redirect"
import {
  endSession,
  isSignedIn,
  startSession,
  useSessionStatus,
  withSessionLock,
} from "@/lib/session"
import { handleError } from "@/utils"
import useCustomToast from "./useCustomToast"

const isLoggedIn = isSignedIn

type UseAuthOptions = {
  /** Where to go after signing in, from the page's `?redirect=`. */
  redirect?: string
}

const useAuth = ({ redirect }: UseAuthOptions = {}) => {
  const navigate = useNavigate()
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
  })

  const login = (data: AccessToken) =>
    withSessionLock(async () => {
      const response = await LoginService.loginAccessToken({
        body: data,
      })
      startSession(response.data.access_token)
    })

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
    endSession()
    try {
      await withSessionLock(() => LoginService.logout())
    } catch {
      /* Sign out locally even if the server can't be reached. */
    }
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
