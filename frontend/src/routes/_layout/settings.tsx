import { createFileRoute } from "@tanstack/react-router"

import { SettingsView } from "@/components/LawPadi/SettingsView"

export const Route = createFileRoute("/_layout/settings")({
  component: SettingsView,
  head: () => ({
    meta: [
      {
        title: "Settings - Law Padi",
      },
    ],
  }),
})
