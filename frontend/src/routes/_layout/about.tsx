import { createFileRoute } from "@tanstack/react-router"
import { PublicInformation } from "@/components/PublicInformation"
import { publicOrigin } from "@/lib/public-origin"
import { staticPageMetadata } from "@/lib/public-pages"
import { seoHead } from "@/lib/seo"
export const Route = createFileRoute("/_layout/about")({
  component: () => <PublicInformation path="/about" />,
  head: () => seoHead(staticPageMetadata("/about", publicOrigin)),
})
