import { useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { toast } from "sonner"

import { startAccountSync } from "@/lib/account-sync"
import i18n from "@/lib/i18n"
import useAuth from "./useAuth"

/** Bring this browser's research into a confirmed account, once per load. */
export function useAccountSync() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const verified = Boolean(user?.email_verified_at)

  useEffect(() => {
    if (!user || !verified) return
    startAccountSync(user)
      .then(({ claimedConversations: count }) => {
        if (count === 0) return
        toast.success(i18n.t("sync.chatsClaimed", { count }))
        void queryClient.invalidateQueries({ queryKey: ["conversations"] })
      })
      .catch(() => {
        toast.error(i18n.t("sync.savedFailed"))
      })
  }, [user, verified, queryClient])
}
