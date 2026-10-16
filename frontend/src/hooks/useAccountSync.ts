import { useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { toast } from "sonner"

import { startAccountSync } from "@/lib/account-sync"
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
        toast.success(
          `Your ${count === 1 ? "chat is" : `${count} chats are`} now in your account.`,
        )
        void queryClient.invalidateQueries({ queryKey: ["conversations"] })
      })
      .catch(() => {
        toast.error(
          "Couldn't sync your saved sections. We'll try again next time.",
        )
      })
  }, [user, verified, queryClient])
}
