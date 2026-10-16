import { useMutation } from "@tanstack/react-query"
import { useState } from "react"
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
  const { user, logout } = useAuth()
  const { showErrorToast } = useCustomToast()
  const [confirmOpen, setConfirmOpen] = useState(false)

  const download = useMutation({
    mutationFn: async () => (await AccountService.exportAccountData()).data,
    onSuccess: (data) => {
      downloadResearch("constitution-ng-account.json", data)
      toast.success("Your account data is downloading")
    },
    onError: handleError.bind(showErrorToast),
  })

  const remove = useMutation({
    mutationFn: () => UsersService.deleteUserMe(),
    onSuccess: () => {
      setConfirmOpen(false)
      toast.success("Your account has been deleted")
      void logout()
    },
    onError: handleError.bind(showErrorToast),
  })

  if (!user) return null

  return (
    <div className="grid gap-5">
      <div className="grid gap-2">
        <p className="text-body font-semibold">Download your data</p>
        <p className="text-sm text-muted-foreground">
          A copy of everything your account holds: your profile, saved sections,
          preferences, and every conversation with its messages.
        </p>
        <div>
          <SquircleButton
            type="button"
            variant="outline"
            loading={download.isPending}
            onClick={() => download.mutate()}
          >
            Download my data
          </SquircleButton>
        </div>
      </div>

      <div className="sq-md grid gap-2 border border-destructive/40 p-4">
        <p className="text-body font-semibold text-destructive">
          Delete your account
        </p>
        {user.is_superuser ? (
          <p className="text-sm text-muted-foreground">
            Administrator accounts can't delete themselves. Ask another
            administrator to remove this account.
          </p>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              This permanently deletes your account, your conversations, saved
              sections and preferences. Download your data first if you want a
              copy.
            </p>
            <div>
              <SquircleButton
                type="button"
                variant="danger"
                onClick={() => setConfirmOpen(true)}
              >
                Delete my account
              </SquircleButton>
            </div>
          </>
        )}
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogTitle>Delete your account?</DialogTitle>
          <DialogDescription>
            Your account, conversations, saved sections and preferences will be
            deleted for good. This can't be undone.
          </DialogDescription>
          <DialogFooter>
            <DialogClose asChild>
              <SquircleButton
                type="button"
                variant="outline"
                disabled={remove.isPending}
              >
                Keep my account
              </SquircleButton>
            </DialogClose>
            <SquircleButton
              type="button"
              variant="danger"
              loading={remove.isPending}
              onClick={() => remove.mutate()}
            >
              Delete my account
            </SquircleButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
