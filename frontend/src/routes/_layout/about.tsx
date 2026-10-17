import { createFileRoute } from "@tanstack/react-router"
import { PublicInformation } from "@/components/PublicInformation"
import { publicOrigin } from "@/lib/public-origin"
import { pageSchema, publicPages, seoHead, websiteSchema } from "@/lib/seo"
export const Route = createFileRoute("/_layout/about")({
  component: () => <PublicInformation path="/about" />,
  head: () => {
    const page = publicPages["/about"]
    const canonical = `${publicOrigin}/about`
    return seoHead({
      ...page,
      canonical,
      index: true,
      schema: [
        websiteSchema(publicOrigin),
        pageSchema(page.title, canonical, page.description),
      ],
    })
  },
})
