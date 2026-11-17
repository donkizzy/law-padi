import { createFileRoute } from "@tanstack/react-router"

import { SavedProvisions } from "@/components/Constitution/SavedProvisions"

export const Route = createFileRoute("/_layout/saved")({
  component: SavedProvisions,
  head: () => ({
    meta: [
      {
        title: "Saved sections - constitution.ng",
      },
    ],
  }),
})
