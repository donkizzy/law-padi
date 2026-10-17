import { createFileRoute } from "@tanstack/react-router"
import { PublicInformation } from "@/components/PublicInformation"
import { publicOrigin } from "@/lib/public-origin"
import { pageSchema, publicPages, seoHead } from "@/lib/seo"
export const Route = createFileRoute("/_layout/methodology")({
  component: () => <PublicInformation path="/methodology" />,
  head: () => {
    const page = publicPages["/methodology"]
    const canonical = `${publicOrigin}/methodology`
    return seoHead({
      ...page,
      canonical,
      index: true,
      schema: [pageSchema(page.title, canonical, page.description)],
    })
  },
})
