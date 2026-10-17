import { createRootRoute, HeadContent, Outlet } from "@tanstack/react-router"
import ErrorComponent from "@/components/Common/ErrorComponent"
import NotFound from "@/components/Common/NotFound"
import { recordNavigation } from "@/lib/landing"
import { SITE_DESCRIPTION, seoHead } from "@/lib/seo"

export const Route = createRootRoute({
  head: () =>
    seoHead({
      title: "constitution.ng",
      description: SITE_DESCRIPTION,
      index: false,
    }),
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
