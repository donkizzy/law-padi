import { Link as RouterLink } from "@tanstack/react-router"
import { FiMessageSquare, FiSearch } from "react-icons/fi"
import { LiaShieldAltSolid } from "react-icons/lia"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import { SquircleButton } from "@/components/LawPadi/primitives"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { recentConversations, sidebarSections } from "@/lib/law-padi-data"
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = sidebarSections[0].items

export function AppSidebar() {
  const { user: currentUser } = useAuth()

  const items = currentUser?.is_superuser
    ? [
        ...baseItems,
        { icon: LiaShieldAltSolid, title: "Legal admin", path: "/admin" },
      ]
    : baseItems

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="gap-5 px-4 py-6 group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-2">
        <Logo variant="responsive" />
        <SquircleButton
          asChild
          className="w-full group-data-[collapsible=icon]:size-10 group-data-[collapsible=icon]:px-0"
        >
          <RouterLink to="/">
            <FiMessageSquare className="size-4" aria-hidden />
            <span className="group-data-[collapsible=icon]:sr-only">
              New conversation
            </span>
          </RouterLink>
        </SquircleButton>
        <label className="sq-sm flex min-h-10 items-center gap-2 border border-sidebar-border bg-background/70 px-3 text-sidebar-foreground/60 group-data-[collapsible=icon]:hidden">
          <FiSearch className="size-4" aria-hidden />
          <span className="sr-only">Search conversations</span>
          <input
            className="min-w-0 flex-1 bg-transparent text-sm text-sidebar-foreground outline-none placeholder:text-sidebar-foreground/50"
            placeholder="Search conversations"
            type="search"
          />
        </label>
      </SidebarHeader>

      <SidebarContent className="gap-5 px-2">
        <Main items={items} />
        <div className="px-2 group-data-[collapsible=icon]:hidden">
          <div className="mb-2 px-2 text-[0.7rem] text-sidebar-foreground/50">
            Recent conversations
          </div>
          <div className="grid gap-1">
            {recentConversations.map((conversation) => (
              <RouterLink
                className="sq-sm block truncate px-3 py-2 text-sm text-sidebar-foreground/65 transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-sidebar-ring/25"
                key={conversation}
                to="/"
              >
                {conversation}
              </RouterLink>
            ))}
          </div>
        </div>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border/80 px-3 py-4">
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
