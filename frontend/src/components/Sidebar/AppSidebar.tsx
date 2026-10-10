import { useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { FiMessageSquare, FiPlus } from "react-icons/fi"
import { LiaShieldAltSolid } from "react-icons/lia"
import { toast } from "sonner"

import { ConversationsService } from "@/client"
import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import { SquircleButton } from "@/components/LawPadi/primitives"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { conversationHeaders, useConversations } from "@/hooks/useConversations"
import { sidebarSections } from "@/lib/law-padi-data"
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = sidebarSections[0].items
  .filter((item) => item.path !== "/amendments")
  .map((item) =>
    item.path === "/" ? { ...item, title: "Search Constitution" } : item,
  )

export function AppSidebar() {
  const { user: currentUser } = useAuth()
  const conversations = useConversations()
  const queryClient = useQueryClient()
  const { isMobile, setOpenMobile } = useSidebar()
  const chatEnabled = conversations.isSuccess

  const items = currentUser?.is_superuser
    ? [
        ...baseItems,
        { icon: LiaShieldAltSolid, title: "Legal admin", path: "/admin" },
      ]
    : baseItems
  if (chatEnabled) items[0] = { ...items[0], title: "Chat" }

  const claim = async () => {
    try {
      const result = await ConversationsService.claimGuestConversations({
        headers: conversationHeaders(),
        withCredentials: true,
      })
      toast.success(
        `${result.data.claimed_count} guest conversation(s) imported`,
      )
      void queryClient.invalidateQueries({ queryKey: ["conversations"] })
    } catch {
      toast.error("Guest conversations could not be imported.")
    }
  }

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="gap-5 px-4 py-6 group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-2">
        <Logo variant="responsive" />
        <SquircleButton
          asChild
          className="w-full group-data-[collapsible=icon]:size-10 group-data-[collapsible=icon]:px-0"
        >
          <RouterLink to="/" search={{ q: undefined, mode: "auto" }}>
            <FiMessageSquare className="size-4" aria-hidden />
            <span className="group-data-[collapsible=icon]:sr-only">
              {chatEnabled ? "New conversation" : "New search"}
            </span>
          </RouterLink>
        </SquircleButton>
      </SidebarHeader>

      <SidebarContent className="gap-5 px-2">
        <Main items={items} />
        {chatEnabled && (
          <SidebarGroup>
            <SidebarGroupLabel>Conversations</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {conversations.data?.pages
                  .flatMap((page) => page.data)
                  .map((conversation) => (
                    <SidebarMenuItem key={conversation.id}>
                      <SidebarMenuButton
                        asChild
                        tooltip={conversation.title || "Conversation"}
                      >
                        <RouterLink
                          onClick={() => isMobile && setOpenMobile(false)}
                          search={{
                            c: conversation.id,
                            q: undefined,
                            mode: "auto",
                            release: undefined,
                          }}
                          to="/"
                        >
                          {/*<FiMessageSquare aria-hidden />*/}
                          <span>{conversation.title || "Conversation"}</span>
                        </RouterLink>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                {conversations.data?.pages[0]?.count === 0 && (
                  <li className="px-2 py-1 text-xs text-muted-foreground">
                    Your chats will appear here.
                  </li>
                )}
                {conversations.hasNextPage && (
                  <li className="px-2 py-1">
                    <button
                      className="w-full text-left text-xs font-semibold text-primary"
                      disabled={conversations.isFetchingNextPage}
                      onClick={() => void conversations.fetchNextPage()}
                      type="button"
                    >
                      {conversations.isFetchingNextPage
                        ? "Loading…"
                        : "Load older conversations"}
                    </button>
                  </li>
                )}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border/80 px-3 py-4">
        {chatEnabled && currentUser && (
          <button
            className="sq-sm flex items-center gap-2 px-2 py-2 text-left text-xs text-muted-foreground hover:bg-sidebar-accent"
            onClick={() => void claim()}
            type="button"
          >
            <FiPlus aria-hidden /> Import guest chats
          </button>
        )}
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
