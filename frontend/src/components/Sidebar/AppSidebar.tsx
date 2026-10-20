import {
  Link as RouterLink,
  useLocation,
  useSearch,
} from "@tanstack/react-router"
import { Fragment, useState } from "react"
import { useTranslation } from "react-i18next"
import {
  FiBookmark,
  FiBookOpen,
  FiMessageSquare,
  FiSearch,
  FiShield,
} from "react-icons/fi"

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
import { useConversations } from "@/hooks/useConversations"
import { intlLocales } from "@/lib/i18n"
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
  const { t, i18n } = useTranslation()
  const { user: currentUser } = useAuth()
  const [historyQuery, setHistoryQuery] = useState("")
  const conversations = useConversations(historyQuery)
  const capabilities = useChatCapabilities()
  const search = useSearch({ strict: false })
  const here = useLocation({ select: (location) => location.href })
  const { isMobile, setOpenMobile } = useSidebar()
  const chatEnabled = capabilities.data?.conversations_enabled === true
  const history = conversations.data?.pages.flatMap((page) => page.data) ?? []

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
  const shortDate = new Intl.DateTimeFormat(
    intlLocales(i18n.resolvedLanguage),
    {
      day: "numeric",
      month: "short",
      timeZone: "Africa/Lagos",
    },
  )

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
            <SidebarGroupLabel>{t("history.title")}</SidebarGroupLabel>
            <SidebarGroupContent>
              <input
                aria-label={t("history.searchLabel")}
                className="sq-sm mb-3 w-full min-w-0 border border-sidebar-border bg-background px-2 py-2 text-xs group-data-[collapsible=icon]:hidden"
                placeholder={t("history.searchPlaceholder")}
                maxLength={200}
                value={historyQuery}
                onChange={(event) => setHistoryQuery(event.target.value)}
              />
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
              <SidebarMenu>
                {history.map((conversation, index) => (
                  <Fragment key={conversation.id}>
                    {(index === 0 ||
                      historyGroup(history[index - 1].updated_at) !==
                        historyGroup(conversation.updated_at)) && (
                      <li className="px-2 pt-2 text-[0.65rem] font-semibold text-muted-foreground group-data-[collapsible=icon]:hidden">
                        {t(`history.${historyGroup(conversation.updated_at)}`)}
                      </li>
                    )}
                    <SidebarMenuItem>
                      <SidebarMenuButton
                        asChild
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
                          {/*<FiMessageSquare aria-hidden />*/}
                          <span className="min-w-0 truncate">
                            {conversation.title || t("history.untitled")}
                            <span className="mt-0.5 block text-[0.65rem] font-normal text-muted-foreground">
                              {shortDate.format(
                                new Date(conversation.updated_at),
                              )}
                            </span>
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

      <SidebarFooter className="border-t border-sidebar-border/80 px-3 py-4">
        {!currentUser && (
          <div className="grid gap-2 px-1 text-xs group-data-[collapsible=icon]:hidden">
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
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
