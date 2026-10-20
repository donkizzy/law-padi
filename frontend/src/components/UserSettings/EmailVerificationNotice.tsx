import { useMutation } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"

import { UsersService } from "@/client"
import { SquircleButton } from "@/components/LawPadi/primitives"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

/** Asks a signed-in person to confirm their email until they have. */
export function EmailVerificationNotice() {
  const { t } = useTranslation("settings")
  const { user } = useAuth()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const resend = useMutation({
    mutationFn: () => UsersService.resendVerificationEmail(),
    onSuccess: () =>
      showSuccessToast(
        user?.email
          ? t("verify.sentTo", { email: user.email })
          : t("verify.sent"),
      ),
    onError: handleError.bind(showErrorToast),
  })

  if (!user || user.email_verified_at) return null

  return (
    <div
      className="sq-md mb-5 grid gap-3 border border-primary/30 bg-primary/5 p-4"
      role="status"
    >
      <div className="grid gap-1">
        <p className="text-body font-semibold">{t("verify.title")}</p>
        <p className="text-sm text-muted-foreground">
          {t("verify.body", { email: user.email })}
        </p>
      </div>
      <div>
        <SquircleButton
          disabled={resend.isPending}
          onClick={() => resend.mutate()}
          size="sm"
          variant="outline"
        >
          {resend.isPending ? t("verify.sending") : t("verify.resend")}
        </SquircleButton>
      </div>
    </div>
  )
}
