import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link as RouterLink } from "@tanstack/react-router"
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
    enabled: Boolean(token),
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
            <h1 className="text-2xl font-bold">Email confirmed</h1>
            <p className="text-body text-muted-foreground">
              Thanks. Your account is ready to keep your research in sync.
            </p>
            <SquircleButton asChild>
              <RouterLink to="/">Continue</RouterLink>
            </SquircleButton>
          </>
        ) : failed ? (
          <>
            <h1 className="text-2xl font-bold">This link didn't work</h1>
            <p className="text-body text-muted-foreground">
              It may have expired or already been replaced by a newer one.
              {signedIn
                ? " You can send yourself a new link from your settings."
                : " Log in to send yourself a new link."}
            </p>
            <SquircleButton asChild>
              {signedIn ? (
                <RouterLink to="/settings">Go to settings</RouterLink>
              ) : (
                <RouterLink to="/login" search={{ redirect: "/settings" }}>
                  Log in
                </RouterLink>
              )}
            </SquircleButton>
          </>
        ) : (
          <p className="text-body" role="status">
            Confirming your email…
          </p>
        )}
      </div>
    </AuthLayout>
  )
}
