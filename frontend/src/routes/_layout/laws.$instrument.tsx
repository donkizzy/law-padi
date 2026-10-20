import { createFileRoute, Outlet } from "@tanstack/react-router"
export const Route = createFileRoute("/_layout/laws/$instrument")({
  component: () => <Outlet />,
})
