import { createFileRoute } from "@tanstack/react-router"

import { BrowseConstitution } from "@/components/LawPadi/BrowseConstitution"

export const Route = createFileRoute("/_layout/constitution/")({
  component: BrowseConstitution,
  head: () => ({
    meta: [
      {
        title: "Browse Constitution - constitution.ng",
      },
    ],
  }),
})
