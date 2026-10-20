import { useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { toast } from "sonner"

import { AccountService, UsersService } from "@/client"
import { SquircleButton } from "@/components/LawPadi/primitives"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { downloadResearch } from "@/lib/research"
import { handleError } from "@/utils"

/** Download everything the account holds, or delete the account. */
export function AccountData() {
  const { t } = useTranslation("settings")
  const { user, logout } = useAuth()
  const { showErrorToast } = useCustomToast()
  const [confirmOpen, setConfirmOpen] = useState(false)

  const download = useMutation({
    mutationFn: async () => (await AccountService.exportAccountData()).data,
    onSuccess: (data) => {
      downloadResearch("constitution-ng-account.json", data)
      toast.success(t("data.downloading"))
    },
    onError: handleError.bind(showErrorToast),
  })

  const remove = useMutation({
    mutationFn: () => UsersService.deleteUserMe(),
    onSuccess: () => {
      setConfirmOpen(false)
      toast.success(t("data.deleted"))
      void logout()
    },
    onError: handleError.bind(showErrorToast),
  })

  if (!user) return null

  return (
    <div className="grid gap-5">
      <div className="grid gap-2">
        <p className="text-body font-semibold">{t("data.downloadTitle")}</p>
        <p className="text-sm text-muted-foreground">
          {t("data.downloadBody")}
        </p>
        <div>
          <SquircleButton
            type="button"
            variant="outline"
            loading={download.isPending}
            onClick={() => download.mutate()}
          >
            {t("data.download")}
          </SquircleButton>
        </div>
      </div>

      <div className="sq-md grid gap-2 border border-destructive/40 p-4">
        <p className="text-body font-semibold text-destructive">
          {t("data.deleteTitle")}
        </p>
        {user.is_superuser ? (
          <p className="text-sm text-muted-foreground">
            {t("data.adminCannotDelete")}
          </p>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              {t("data.deleteBody")}
            </p>
            <div>
              <SquircleButton
                type="button"
                variant="danger"
                onClick={() => setConfirmOpen(true)}
              >
                {t("data.delete")}
              </SquircleButton>
            </div>
          </>
        )}
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogTitle>{t("data.confirmTitle")}</DialogTitle>
          <DialogDescription>{t("data.confirmBody")}</DialogDescription>
          <DialogFooter>
            <DialogClose asChild>
              <SquircleButton
                type="button"
                variant="outline"
                disabled={remove.isPending}
              >
                {t("data.keep")}
              </SquircleButton>
            </DialogClose>
            <SquircleButton
              type="button"
              variant="danger"
              loading={remove.isPending}
              onClick={() => remove.mutate()}
            >
              {t("data.delete")}
            </SquircleButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
