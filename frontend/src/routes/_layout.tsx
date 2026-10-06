import {
  createFileRoute,
  Outlet,
  Link as RouterLink,
} from "@tanstack/react-router"
import { FiMessageSquare, FiSearch, FiSettings } from "react-icons/fi"

import { Appearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import { SquircleButton } from "@/components/LawPadi/primitives"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"

export const Route = createFileRoute("/_layout")({
  component: Layout,
})

function Layout() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="min-h-svh bg-background">
        <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b border-border/80 bg-background/85 px-4 backdrop-blur-xl sm:px-6">
          <SidebarTrigger className="-ml-1 text-muted-foreground" />
          <div className="md:hidden">
            <Logo variant="full" />
          </div>
          <div className="hidden min-w-0 items-center gap-2 text-xs font-semibold text-muted-foreground sm:flex">
            <span>Explore the Constitution</span>
            <span aria-hidden className="sq-xs size-1.5 bg-primary" />
            <span>Sources always visible</span>
          </div>

          <div className="ml-auto flex items-center gap-1.5">
            <SquircleButton
              asChild
              className="hidden sm:inline-flex"
              size="sm"
              variant="ghost"
            >
              <RouterLink to="/" search={{ q: undefined, mode: "auto" }}>
                <FiMessageSquare className="size-4" aria-hidden />
                New
              </RouterLink>
            </SquircleButton>
            <SquircleButton
              asChild
              className="hidden px-3 md:inline-flex"
              size="sm"
              variant="ghost"
            >
              <RouterLink to="/constitution">
                <FiSearch className="size-4" aria-hidden />
                Search
              </RouterLink>
            </SquircleButton>
            <Appearance />
            <SquircleButton
              asChild
              aria-label="Open settings"
              className="size-10 px-0"
              size="sm"
              variant="ghost"
            >
              <RouterLink to="/settings">
                <FiSettings className="size-4" aria-hidden />
                <span className="sr-only">Settings</span>
              </RouterLink>
            </SquircleButton>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-hidden">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
