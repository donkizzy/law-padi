import { createFileRoute } from "@tanstack/react-router"
import { LandingPage } from "@/components/Landing/LandingPage"
import { faqs } from "@/lib/public-content"
import { publicOrigin } from "@/lib/public-origin"
import { pageSchema, SITE_DESCRIPTION, seoHead, websiteSchema } from "@/lib/seo"
export const Route = createFileRoute("/welcome")({
  component: LandingPage,
  head: () =>
    seoHead({
      title: "Nigeria's Constitution and published laws | constitution.ng",
      description: SITE_DESCRIPTION,
      canonical: `${publicOrigin}/welcome`,
      index: true,
      schema: [
        {
          "@context": "https://schema.org",
          "@type": "FAQPage",
          mainEntity: faqs.map((item) => ({
            "@type": "Question",
            name: item.q,
            acceptedAnswer: { "@type": "Answer", text: item.a },
          })),
        },
        websiteSchema(publicOrigin),
        pageSchema(
          "Nigeria's Constitution and published laws",
          `${publicOrigin}/welcome`,
          SITE_DESCRIPTION,
        ),
      ],
    }),
})
