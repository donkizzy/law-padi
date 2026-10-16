import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"

import { LawPadiHome } from "@/components/LawPadi/LawPadiHome"

export const Route = createFileRoute("/_layout/")({
  validateSearch: z.object({
    c: z.uuid().optional(),
    q: z.string().trim().max(2000).optional(),
    mode: z.enum(["auto", "semantic"]).optional(),
    release: z.string().max(128).optional(),
    selected: z.uuid().optional(),
    intent: z.enum(["ask", "find"]).optional(),
    fresh: z.uuid().optional(),
  }),
  component: LawPadiHome,
  head: () => ({
    meta: [
      {
        title: "constitution.ng - Explore Nigeria's Constitution",
      },
    ],
  }),
})
