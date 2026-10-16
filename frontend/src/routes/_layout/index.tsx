import { createFileRoute, redirect } from "@tanstack/react-router"
import { z } from "zod"

import { LawPadiHome } from "@/components/LawPadi/LawPadiHome"
import { isLoggedIn } from "@/hooks/useAuth"
import { isLandingNavigation } from "@/lib/landing"

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
  // Guests who land on the bare home URL see the welcome page first.
  // Signed-in visitors, deep links (/?q=…) and in-app navigation go straight to chat.
  beforeLoad: ({ search }) => {
    const isBareHome = Object.values(search).every((value) => value == null)
    if (isBareHome && isLandingNavigation() && !isLoggedIn()) {
      throw redirect({ to: "/welcome", replace: true })
    }
  },
  component: LawPadiHome,
  head: () => ({
    meta: [
      {
        title: "constitution.ng - Explore Nigeria's Constitution",
      },
    ],
  }),
})
