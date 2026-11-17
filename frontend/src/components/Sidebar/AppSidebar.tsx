import {
  Link as RouterLink,
  useLocation,
  useSearch,
} from "@tanstack/react-router"
import { Fragment, useEffect, useId, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import {
  FiBookmark,
  FiBookOpen,
  FiMessageSquare,
  FiSearch,
  FiShield,
  FiX,
} from "react-icons/fi"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import { NewConversationButton } from "@/components/Constitution/NewConversationButton"
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
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { useChatCapabilities } from "@/hooks/useChatCapabilities"
import { useConversations } from "@/hooks/useConversations"
import { type Item, Main } from "./Main"
import { User } from "./User"

// Not shown: en-CA formats as YYYY-MM-DD, which compares days in Lagos time.
const historyDay = new Intl.DateTimeFormat("en-CA", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  timeZone: "Africa/Lagos",
})

function historyGroup(updatedAt: string) {
  const day = historyDay.format(new Date(updatedAt))
  if (day === historyDay.format(new Date())) return "today"
  if (day === historyDay.format(new Date(Date.now() - 86_400_000)))
    return "yesterday"
  return "earlier"
}

export function AppSidebar() {
  const { t } = useTranslation()
  const { user: currentUser } = useAuth()
  const [historyQuery, setHistoryQuery] = useState("")
  const [searchOpen, setSearchOpen] = useState(false)
  const searchRef = useRef<HTMLInputElement>(null)
  const searchButtonRef = useRef<HTMLButtonElement>(null)
  const searchId = useId()
  const conversations = useConversations(historyQuery)
  const capabilities = useChatCapabilities()
  const search = useSearch({ strict: false })
  const here = useLocation({ select: (location) => location.href })
  const { isMobile, setOpenMobile, state } = useSidebar()
  const chatEnabled = capabilities.data?.conversations_enabled === true
  const history = conversations.data?.pages.flatMap((page) => page.data) ?? []

  useEffect(() => {
    if (searchOpen) searchRef.current?.focus()
  }, [searchOpen])

  useEffect(() => {
    if (state === "collapsed" && !isMobile) {
      setSearchOpen(false)
      setHistoryQuery("")
    }
  }, [state, isMobile])

  const closeSearch = () => {
    setSearchOpen(false)
    setHistoryQuery("")
    requestAnimationFrame(() => searchButtonRef.current?.focus())
  }

  const navigation: Item[] = [
    {
      icon: FiMessageSquare,
      title: t("nav.ask"),
      path: "/",
      intent: "ask",
    },
    { icon: FiSearch, title: t("nav.findSection"), path: "/", intent: "find" },
    { icon: FiBookOpen, title: t("nav.browseLaws"), path: "/laws" },
    { icon: FiBookmark, title: t("nav.saved"), path: "/saved" },
  ]
  const items = currentUser?.is_superuser
    ? [
        ...navigation,
        { icon: FiShield, title: t("nav.legalAdmin"), path: "/admin" },
      ]
    : navigation

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-2 py-3">
        <div className="flex h-9 items-center justify-between gap-2 pl-2 group-data-[collapsible=icon]:justify-start group-data-[collapsible=icon]:pl-0">
          <div className="min-w-0 group-data-[collapsible=icon]:hidden">
            <Logo variant="responsive" />
          </div>
          <SidebarTrigger className="size-8 shrink-0 text-muted-foreground max-md:hidden" />
        </div>
      </SidebarHeader>

      <SidebarContent className="gap-0 px-2">
        <div className="mb-3">
          <NewConversationButton className="w-full group-data-[collapsible=icon]:size-8 group-data-[collapsible=icon]:min-h-8 group-data-[collapsible=icon]:p-2" />
        </div>
        <Main items={items} />
        {chatEnabled && (
          <SidebarGroup className="mt-4 px-0 group-data-[collapsible=icon]:hidden">
            <div className="relative mb-1 h-9">
              <SidebarGroupLabel className="h-9 pr-10 text-muted-foreground">
                {t("history.title")}
              </SidebarGroupLabel>
              <button
                ref={searchButtonRef}
                type="button"
                aria-label={t("history.searchLabel")}
                aria-expanded={searchOpen}
                aria-controls={searchId}
                onClick={() => setSearchOpen(true)}
                className={`sq-xs absolute right-0 top-0 grid size-9 place-items-center text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${searchOpen ? "invisible" : ""}`}
              >
                <FiSearch className="size-4" aria-hidden />
              </button>
              <div
                id={searchId}
                inert={!searchOpen}
                className={`sq-xs absolute right-0 top-0 flex h-9 items-center overflow-hidden border border-sidebar-border bg-background transition-[width,opacity] duration-200 focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/25 ${searchOpen ? "visible w-full opacity-100" : "invisible pointer-events-none w-9 opacity-0"}`}
              >
                <FiSearch
                  className="ml-2 size-4 shrink-0 text-muted-foreground"
                  aria-hidden
                />
                <input
                  ref={searchRef}
                  aria-label={t("history.searchLabel")}
                  className="min-w-0 flex-1 bg-transparent px-2 text-label font-normal outline-none placeholder:text-muted-foreground"
                  placeholder={t("history.searchPlaceholder")}
                  maxLength={200}
                  value={historyQuery}
                  onChange={(event) => setHistoryQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      event.preventDefault()
                      closeSearch()
                    }
                  }}
                />
                <button
                  type="button"
                  aria-label={t("actions.close")}
                  onClick={closeSearch}
                  className="sq-xs grid size-8 shrink-0 place-items-center text-muted-foreground hover:bg-sidebar-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                >
                  <FiX className="size-4" aria-hidden />
                </button>
              </div>
            </div>
            <SidebarGroupContent>
              {conversations.isError && (
                <div className="px-2 py-2 text-xs" role="alert">
                  {t("history.loadFailed")}{" "}
                  <button
                    className="min-h-9 font-semibold text-primary"
                    type="button"
                    onClick={() => void conversations.refetch()}
                  >
                    {t("actions.tryAgain")}
                  </button>
                </div>
              )}
              {conversations.isPending && (
                <p
                  className="px-2 py-2 text-xs text-muted-foreground"
                  role="status"
                >
                  {t("history.loading")}
                </p>
              )}
              <SidebarMenu className="gap-1">
                {history.map((conversation, index) => (
                  <Fragment key={conversation.id}>
                    {(index === 0 ||
                      historyGroup(history[index - 1].updated_at) !==
                        historyGroup(conversation.updated_at)) && (
                      <li className="px-2 pb-1 pt-3 text-label font-medium text-muted-foreground">
                        {t(`history.${historyGroup(conversation.updated_at)}`)}
                      </li>
                    )}
                    <SidebarMenuItem>
                      <SidebarMenuButton
                        asChild
                        className="sq-xs h-9 px-2 font-medium text-sidebar-foreground/80 transition-colors"
                        tooltip={conversation.title || t("history.untitled")}
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
                          <span className="min-w-0 flex-1 truncate leading-5">
                            {conversation.title || t("history.untitled")}
                          </span>
                        </RouterLink>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  </Fragment>
                ))}
                {conversations.data?.pages[0]?.count === 0 && (
                  <li className="px-2 py-1 text-xs text-muted-foreground">
                    {historyQuery ? t("history.noMatches") : t("history.empty")}
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
                        ? t("status.loading")
                        : t("history.loadOlder")}
                    </button>
                  </li>
                )}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter className="mx-2 gap-2 border-t border-sidebar-border/80 px-0 py-3">
        {!currentUser && (
          <div className="grid gap-2 px-2 text-xs group-data-[collapsible=icon]:hidden">
            <p className="text-muted-foreground">{t("guest.note")}</p>
            <div className="flex gap-2">
              <RouterLink
                className="sq-sm min-h-9 px-2 py-2 font-semibold text-primary hover:underline"
                to="/login"
                search={{ redirect: here }}
                onClick={() => setOpenMobile(false)}
              >
                {t("auth.signIn")}
              </RouterLink>
              <RouterLink
                className="sq-sm min-h-9 px-2 py-2 font-semibold text-primary hover:underline"
                to="/signup"
                search={{ redirect: here }}
                onClick={() => setOpenMobile(false)}
              >
                {t("auth.createAccount")}
              </RouterLink>
            </div>
          </div>
        )}
        <SidebarMenu>
          <SidebarAppearance />
        </SidebarMenu>
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
