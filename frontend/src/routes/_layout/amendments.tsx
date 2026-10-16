import { createFileRoute } from "@tanstack/react-router"

import { AmendmentsView } from "@/components/LawPadi/AmendmentsView"

export const Route = createFileRoute("/_layout/amendments")({
  component: AmendmentsView,
  head: () => ({
    meta: [
      {
        title: "Amendments - constitution.ng",
      },
    ],
  }),
})
