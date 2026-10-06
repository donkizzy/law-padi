import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"

import { LawPadiHome } from "@/components/LawPadi/LawPadiHome"

export const Route = createFileRoute("/_layout/")({
  validateSearch: z.object({
    q: z.string().trim().max(2000).optional(),
    mode: z.enum(["auto", "semantic"]).optional(),
  }),
  component: LawPadiHome,
  head: () => ({
    meta: [
      {
        title: "Law Padi - Explore Nigeria's Constitution",
      },
    ],
  }),
})
