import {
  Link as RouterLink,
  useRouterState,
  useSearch,
} from "@tanstack/react-router"
import type { IconType } from "react-icons"
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { useChatCapabilities } from "@/hooks/useChatCapabilities"

export type Item = {
  icon: IconType
  title: string
  path: string
  count?: string
  intent?: "ask" | "find"
}

interface MainProps {
  items: Item[]
}

export function Main({ items }: MainProps) {
  const { isMobile, setOpenMobile } = useSidebar()
  const router = useRouterState()
  const search = useSearch({ strict: false })
  const capabilities = useChatCapabilities()
  const currentPath = router.location.pathname

  const handleMenuClick = () => {
    if (isMobile) {
      setOpenMobile(false)
    }
  }

  return (
    <SidebarGroup className="px-0">
      <SidebarGroupContent>
        <SidebarMenu className="gap-1">
          {items.map((item) => {
            const isActive =
              (currentPath === item.path &&
                (!item.intent ||
                  (search.intent ??
                    (capabilities.data?.conversations_enabled
                      ? "ask"
                      : "find")) === item.intent)) ||
              (item.path !== "/" && currentPath.startsWith(item.path))

            return (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  className="sq-xs h-9 gap-2 px-2 font-medium text-sidebar-foreground/80 transition-colors [&>svg]:size-4"
                  tooltip={item.title}
                  isActive={isActive}
                  asChild
                >
                  <RouterLink
                    to={item.path}
                    search={item.intent ? { intent: item.intent } : undefined}
                    onClick={handleMenuClick}
                    activeOptions={{ includeSearch: true }}
                  >
                    <item.icon aria-hidden />
                    <span className="min-w-0 flex-1 truncate">
                      {item.title}
                    </span>
                    {item.count ? (
                      <span className="ml-auto text-xs text-muted-foreground">
                        {item.count}
                      </span>
                    ) : null}
                  </RouterLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}
