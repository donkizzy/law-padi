import { useMutation } from "@tanstack/react-query"

import { UsersService } from "@/client"
import { SquircleButton } from "@/components/LawPadi/primitives"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

/** Asks a signed-in person to confirm their email until they have. */
export function EmailVerificationNotice() {
  const { user } = useAuth()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const resend = useMutation({
    mutationFn: () => UsersService.resendVerificationEmail(),
    onSuccess: () =>
      showSuccessToast(`We sent a new link to ${user?.email ?? "your email"}.`),
    onError: handleError.bind(showErrorToast),
  })

  if (!user || user.email_verified_at) return null

  return (
    <div
      className="sq-md mb-5 grid gap-3 border border-primary/30 bg-primary/5 p-4"
      role="status"
    >
      <div className="grid gap-1">
        <p className="text-body font-semibold">Confirm your email address</p>
        <p className="text-sm text-muted-foreground">
          We sent a link to {user.email}. Your saved sections and conversations
          start syncing once it's confirmed.
        </p>
      </div>
      <div>
        <SquircleButton
          disabled={resend.isPending}
          onClick={() => resend.mutate()}
          size="sm"
          variant="outline"
        >
          {resend.isPending ? "Sending…" : "Send a new link"}
        </SquircleButton>
      </div>
    </div>
  )
}
