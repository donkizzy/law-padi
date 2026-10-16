import { useNavigate } from "@tanstack/react-router"
import { FiMessageSquare } from "react-icons/fi"
import { useSidebar } from "@/components/ui/sidebar"
import { draftPrefix } from "@/hooks/useWorkspacePreferences"
import {
  cancelChatRequests,
  requestComposerFocusAfterDrawer,
} from "@/lib/chat-navigation"
import { SquircleButton } from "./primitives"

export function NewConversationButton({
  compact = false,
  className,
}: {
  compact?: boolean
  className?: string
}) {
  const navigate = useNavigate()
  const { setOpenMobile, isMobile } = useSidebar()
  return (
    <SquircleButton
      className={className}
      size={compact ? "sm" : "md"}
      variant={compact ? "ghost" : "primary"}
      aria-label="New conversation"
      type="button"
      onClick={() => {
        cancelChatRequests()
        if (isMobile) requestComposerFocusAfterDrawer()
        try {
          sessionStorage.removeItem(`${draftPrefix}new`)
          sessionStorage.removeItem(`${draftPrefix}find`)
        } catch {
          /* Navigation does not require browser storage. */
        }
        setOpenMobile(false)
        void navigate({
          to: "/",
          search: {
            c: undefined,
            q: undefined,
            mode: "auto",
            release: undefined,
            selected: undefined,
            intent: "ask",
            fresh: crypto.randomUUID(),
          },
        })
      }}
    >
      <FiMessageSquare className="size-4" aria-hidden />
      <span
        className={
          compact ? undefined : "group-data-[collapsible=icon]:sr-only"
        }
      >
        {compact ? "New" : "New conversation"}
      </span>
    </SquircleButton>
  )
}
