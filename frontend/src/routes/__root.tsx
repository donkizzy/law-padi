import { createRootRoute, HeadContent, Outlet } from "@tanstack/react-router"
import ErrorComponent from "@/components/Common/ErrorComponent"
import NotFound from "@/components/Common/NotFound"
import { recordNavigation } from "@/lib/landing"

export const Route = createRootRoute({
  beforeLoad: ({ cause }) => {
    if (cause !== "preload") recordNavigation()
  },
  component: () => (
    <>
      <HeadContent />
      <Outlet />
    </>
  ),
  notFoundComponent: () => <NotFound />,
  errorComponent: () => <ErrorComponent />,
})
