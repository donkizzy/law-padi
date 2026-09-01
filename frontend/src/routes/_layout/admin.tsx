import { createFileRoute } from "@tanstack/react-router"

import { AdminWorkspace } from "@/components/LawPadi/AdminWorkspace"

export const Route = createFileRoute("/_layout/admin")({
  component: AdminWorkspace,
  head: () => ({
    meta: [
      {
        title: "Legal Admin - Law Padi",
      },
    ],
  }),
})
