import { createFileRoute } from "@tanstack/react-router"

import { LawPadiHome } from "@/components/LawPadi/LawPadiHome"

export const Route = createFileRoute("/_layout/")({
  component: LawPadiHome,
  head: () => ({
    meta: [
      {
        title: "Law Padi - Nigerian Constitution AI",
      },
    ],
  }),
})
