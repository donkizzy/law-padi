import { createFileRoute, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { AdminWorkspace } from "@/components/LawPadi/AdminWorkspace"
import { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/admin")({
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({ to: "/login" })
    }
    await UsersService.readUserMe()
  },
  component: AdminWorkspace,
  head: () => ({
    meta: [
      {
        title: "Legal Admin - Law Padi",
      },
    ],
  }),
})
