import {
  createFileRoute,
  Outlet,
  Link as RouterLink,
} from "@tanstack/react-router"
import { useTranslation } from "react-i18next"
import { FiSearch, FiSettings } from "react-icons/fi"

import { Appearance } from "@/components/Common/Appearance"
import { LanguageMenu } from "@/components/Common/LanguagePicker"
import { Logo } from "@/components/Common/Logo"
import { NewConversationButton } from "@/components/LawPadi/NewConversationButton"
import { SquircleButton } from "@/components/LawPadi/primitives"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { useAccountSync } from "@/hooks/useAccountSync"

export const Route = createFileRoute("/_layout")({
  component: Layout,
})

function Layout() {
  const { t } = useTranslation()
  useAccountSync()
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
            <span>{t("header.explore")}</span>
            <span aria-hidden className="sq-xs size-1.5 bg-primary" />
            <span>{t("header.sources")}</span>
          </div>

          <div className="ml-auto flex items-center gap-1.5">
            <NewConversationButton compact className="hidden sm:inline-flex" />
            <SquircleButton
              asChild
              className="hidden px-3 md:inline-flex"
              size="sm"
              variant="ghost"
            >
              <RouterLink to="/" search={{ intent: "find" }}>
                <FiSearch className="size-4" aria-hidden />
                {t("nav.findSection")}
              </RouterLink>
            </SquircleButton>
            <LanguageMenu />
            {/* Phones switch theme from the sidebar, leaving room for language. */}
            <div className="hidden sm:block">
              <Appearance />
            </div>
            <SquircleButton
              asChild
              aria-label={t("header.openSettings")}
              className="size-10 px-0"
              size="sm"
              variant="ghost"
            >
              <RouterLink to="/settings">
                <FiSettings className="size-4" aria-hidden />
                <span className="sr-only">{t("nav.settings")}</span>
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
