import { Link as RouterLink } from "@tanstack/react-router"
import { FiMessageSquare } from "react-icons/fi"
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
          <RouterLink to="/" search={{ q: undefined, mode: "auto" }}>
            <FiMessageSquare className="size-4" aria-hidden />
            <span className="group-data-[collapsible=icon]:sr-only">
              New search
            </span>
          </RouterLink>
        </SquircleButton>
      </SidebarHeader>

      <SidebarContent className="gap-5 px-2">
        <Main items={items} />
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border/80 px-3 py-4">
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
