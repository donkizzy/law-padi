import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"
import { BrowseConstitution } from "@/components/Constitution/BrowseConstitution"
import { SITE_DESCRIPTION, seoHead } from "@/lib/seo"
export const Route = createFileRoute("/_layout/laws/")({
  validateSearch: z.object({ release: z.string().max(128).optional() }),
  component: () => <BrowseConstitution release={Route.useSearch().release} />,
  head: () =>
    seoHead({
      title: "Browse published laws | constitution.ng",
      description: SITE_DESCRIPTION,
      index: false,
    }),
})
