import landing from "../locales/en/landing.json"
import {
  pageSchema,
  publicPages,
  type SeoMetadata,
  SITE_DESCRIPTION,
  websiteSchema,
} from "./seo"

/**
 * Metadata for the public pages that the browser routes and the edge Worker
 * both render. Each page is defined here once, so a title, description or
 * JSON-LD change reaches the crawler-facing HTML and the hydrated app together.
 */

// English FAQ: the landing catalogue is the source, shared with the Worker.
export const faqs = landing.faq.items

/** The landing headline: the two hero lines read as one sentence pair. */
export const LANDING_HEADLINE = `${landing.hero.line1} ${landing.hero.line2}`

const LANDING_TITLE =
  "Nigeria's Constitution and published laws | constitution.ng"

export function landingMetadata(origin: string): SeoMetadata {
  const canonical = `${origin}/welcome`
  return {
    title: LANDING_TITLE,
    description: SITE_DESCRIPTION,
    canonical,
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
      websiteSchema(origin),
      pageSchema(LANDING_TITLE, canonical, SITE_DESCRIPTION),
    ],
  }
}

export function staticPageMetadata(
  path: keyof typeof publicPages,
  origin: string,
): SeoMetadata {
  const page = publicPages[path]
  const canonical = origin + path
  return {
    title: page.title,
    description: page.description,
    canonical,
    index: true,
    schema: [
      websiteSchema(origin),
      pageSchema(page.title, canonical, page.description),
    ],
  }
}

/** The amendments route is retired: it is never indexed. */
export const amendmentsMetadata: SeoMetadata = {
  title: "Amendments unavailable | constitution.ng",
  description: "Reviewed amendment records are not published here yet.",
  index: false,
}
