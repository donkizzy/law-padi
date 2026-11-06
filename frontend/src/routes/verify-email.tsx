import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link as RouterLink } from "@tanstack/react-router"
import { useTranslation } from "react-i18next"
import { z } from "zod"

import { UsersService } from "@/client"
import { AuthLayout } from "@/components/Common/AuthLayout"
import { SquircleButton } from "@/components/LawPadi/primitives"
import { useSessionStatus } from "@/lib/session"

export const Route = createFileRoute("/verify-email")({
  component: VerifyEmail,
  validateSearch: z.object({
    token: z.string().max(2048).optional().catch(undefined),
  }),
  head: () => ({
    meta: [{ title: "Confirm your email - constitution.ng" }],
  }),
})

function VerifyEmail() {
  const { t } = useTranslation("auth")
  const { token } = Route.useSearch()
  const queryClient = useQueryClient()
  const signedIn = useSessionStatus() === "signed-in"
  // Confirming is idempotent, so a query (one request per token, kept across
  // remounts) fits better than a mutation fired from an effect.
  const verify = useQuery({
    queryKey: ["verifyEmail", token],
    queryFn: async () => {
      const response = await UsersService.verifyEmail({
        body: { token: token ?? "" },
      })
      await queryClient.invalidateQueries({ queryKey: ["currentUser"] })
      return response.data
    },
    enabled: false,
    retry: false,
    staleTime: Number.POSITIVE_INFINITY,
    refetchOnWindowFocus: false,
  })

  const failed = !token || verify.isError

  return (
    <AuthLayout>
      <div className="flex flex-col gap-4 text-center" aria-live="polite">
        {verify.isSuccess ? (
          <>
            <h1 className="text-2xl font-bold">{t("verify.confirmed")}</h1>
            <p className="text-body text-muted-foreground">
              {t("verify.confirmedBody")}
            </p>
            <SquircleButton asChild>
              <RouterLink to="/">{t("verify.continue")}</RouterLink>
            </SquircleButton>
          </>
        ) : failed ? (
          <>
            <h1 className="text-2xl font-bold">{t("verify.failed")}</h1>
            <p className="text-body text-muted-foreground">
              {t("verify.failedBody")}{" "}
              {signedIn ? t("verify.resendSettings") : t("verify.resendLogin")}
            </p>
            <SquircleButton asChild>
              {signedIn ? (
                <RouterLink to="/settings">
                  {t("verify.goToSettings")}
                </RouterLink>
              ) : (
                <RouterLink to="/login" search={{ redirect: "/settings" }}>
                  {t("logIn")}
                </RouterLink>
              )}
            </SquircleButton>
          </>
        ) : verify.isFetching ? (
          <p className="text-body" role="status">
            {t("verify.confirming")}
          </p>
        ) : (
          <SquircleButton type="button" onClick={() => void verify.refetch()}>
            {t("verify.confirm")}
          </SquircleButton>
        )}
      </div>
    </AuthLayout>
  )
}
