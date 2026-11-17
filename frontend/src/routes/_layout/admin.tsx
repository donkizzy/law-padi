import { createFileRoute, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { AdminWorkspace } from "@/components/Constitution/admin/AdminWorkspace"
import { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/admin")({
  beforeLoad: async ({ location }) => {
    if (!isLoggedIn()) {
      throw redirect({ to: "/login", search: { redirect: location.href } })
    }
    await UsersService.readUserMe()
  },
  component: AdminWorkspace,
  head: () => ({
    meta: [
      {
        title: "Legal Admin - constitution.ng",
      },
    ],
  }),
})
