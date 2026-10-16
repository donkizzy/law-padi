import { useQueryClient } from "@tanstack/react-query"
import {
  Link as RouterLink,
  useLocation,
  useSearch,
} from "@tanstack/react-router"
import { Fragment, useState } from "react"
import { FiMessageSquare, FiPlus, FiSearch } from "react-icons/fi"
import { LiaShieldAltSolid } from "react-icons/lia"
import { toast } from "sonner"
import { ConversationsService } from "@/client"
import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import { NewConversationButton } from "@/components/LawPadi/NewConversationButton"
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
import { useChatCapabilities } from "@/hooks/useChatCapabilities"
import { conversationHeaders, useConversations } from "@/hooks/useConversations"
import { sidebarSections } from "@/lib/law-padi-data"
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = sidebarSections[0].items
  .filter((item) => item.path !== "/amendments" && item.path !== "/")
  .map((item) =>
    item.path === "/" ? { ...item, title: "Search Constitution" } : item,
  )

const historyDay = new Intl.DateTimeFormat("en-CA", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  timeZone: "Africa/Lagos",
})

function historyGroup(updatedAt: string) {
  const day = historyDay.format(new Date(updatedAt))
  if (day === historyDay.format(new Date())) return "Today"
  if (day === historyDay.format(new Date(Date.now() - 86_400_000)))
    return "Yesterday"
  return "Earlier"
}

export function AppSidebar() {
  const { user: currentUser } = useAuth()
  const [historyQuery, setHistoryQuery] = useState("")
  const conversations = useConversations(historyQuery)
  const capabilities = useChatCapabilities()
  const search = useSearch({ strict: false })
  const here = useLocation({ select: (location) => location.href })
  const queryClient = useQueryClient()
  const { isMobile, setOpenMobile } = useSidebar()
  const chatEnabled = capabilities.data?.conversations_enabled === true
  const history = conversations.data?.pages.flatMap((page) => page.data) ?? []

  const navigation: Item[] = [
    {
      icon: FiMessageSquare,
      title: "Ask a question",
      path: "/",
      intent: "ask",
    },
    { icon: FiSearch, title: "Find a section", path: "/", intent: "find" },
    ...baseItems,
  ]
  const items = currentUser?.is_superuser
    ? [
        ...navigation,
        { icon: LiaShieldAltSolid, title: "Legal admin", path: "/admin" },
      ]
    : navigation

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
        <NewConversationButton className="w-full group-data-[collapsible=icon]:size-10 group-data-[collapsible=icon]:px-0" />
      </SidebarHeader>

      <SidebarContent className="gap-5 px-2">
        <Main items={items} />
        {chatEnabled && (
          <SidebarGroup>
            <SidebarGroupLabel>Conversations</SidebarGroupLabel>
            <SidebarGroupContent>
              <input
                aria-label="Search conversations"
                className="sq-sm mb-3 w-full min-w-0 border border-sidebar-border bg-background px-2 py-2 text-xs group-data-[collapsible=icon]:hidden"
                placeholder="Search your chats"
                maxLength={200}
                value={historyQuery}
                onChange={(event) => setHistoryQuery(event.target.value)}
              />
              {conversations.isError && (
                <div className="px-2 py-2 text-xs" role="alert">
                  History couldn't load.{" "}
                  <button
                    className="min-h-9 font-semibold text-primary"
                    type="button"
                    onClick={() => void conversations.refetch()}
                  >
                    Try again
                  </button>
                </div>
              )}
              {conversations.isPending && (
                <p
                  className="px-2 py-2 text-xs text-muted-foreground"
                  role="status"
                >
                  Loading chats…
                </p>
              )}
              <SidebarMenu>
                {history.map((conversation, index) => (
                  <Fragment key={conversation.id}>
                    {(index === 0 ||
                      historyGroup(history[index - 1].updated_at) !==
                        historyGroup(conversation.updated_at)) && (
                      <li className="px-2 pt-2 text-[0.65rem] font-semibold text-muted-foreground group-data-[collapsible=icon]:hidden">
                        {historyGroup(conversation.updated_at)}
                      </li>
                    )}
                    <SidebarMenuItem>
                      <SidebarMenuButton
                        asChild
                        tooltip={conversation.title || "Conversation"}
                        isActive={search.c === conversation.id}
                      >
                        <RouterLink
                          onClick={() => isMobile && setOpenMobile(false)}
                          activeOptions={{ includeSearch: true }}
                          aria-current={
                            search.c === conversation.id ? "page" : undefined
                          }
                          search={{
                            c: conversation.id,
                            q: undefined,
                            mode: "auto",
                            release: undefined,
                            selected: undefined,
                            intent: "ask",
                            fresh: undefined,
                          }}
                          to="/"
                        >
                          {/*<FiMessageSquare aria-hidden />*/}
                          <span className="min-w-0 truncate">
                            {conversation.title || "Conversation"}
                            <span className="mt-0.5 block text-[0.65rem] font-normal text-muted-foreground">
                              {new Intl.DateTimeFormat("en-NG", {
                                day: "numeric",
                                month: "short",
                                timeZone: "Africa/Lagos",
                              }).format(new Date(conversation.updated_at))}
                            </span>
                          </span>
                        </RouterLink>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  </Fragment>
                ))}
                {conversations.data?.pages[0]?.count === 0 && (
                  <li className="px-2 py-1 text-xs text-muted-foreground">
                    {historyQuery
                      ? "No chats match that search."
                      : "Your chats will appear here."}
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
            <FiPlus aria-hidden /> Bring guest chats into this account
          </button>
        )}
        {!currentUser && (
          <div className="grid gap-2 px-1 text-xs group-data-[collapsible=icon]:hidden">
            <p className="text-muted-foreground">
              Guest · bookmarks stay on this browser.
            </p>
            <div className="flex gap-2">
              <RouterLink
                className="sq-sm min-h-9 px-2 py-2 font-semibold text-primary hover:underline"
                to="/login"
                search={{ redirect: here }}
                onClick={() => setOpenMobile(false)}
              >
                Sign in
              </RouterLink>
              <RouterLink
                className="sq-sm min-h-9 px-2 py-2 font-semibold text-primary hover:underline"
                to="/signup"
                search={{ redirect: here }}
                onClick={() => setOpenMobile(false)}
              >
                Create account
              </RouterLink>
            </div>
          </div>
        )}
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
