import { createFileRoute } from "@tanstack/react-router"
import { LandingPage } from "@/components/Landing/LandingPage"
import { publicOrigin } from "@/lib/public-origin"
import { landingMetadata } from "@/lib/public-pages"
import { seoHead } from "@/lib/seo"
export const Route = createFileRoute("/welcome")({
  component: LandingPage,
  head: () => seoHead(landingMetadata(publicOrigin)),
})
