import { createFileRoute } from "@tanstack/react-router"

import { SavedProvisions } from "@/components/LawPadi/SavedProvisions"

export const Route = createFileRoute("/_layout/saved")({
  component: SavedProvisions,
  head: () => ({
    meta: [
      {
        title: "Saved Provisions - Law Padi",
      },
    ],
  }),
})
