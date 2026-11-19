import edition from "../locales/en/edition.json"
import pages from "../locales/en/pages.json"

/** Public identity shared by the browser and the Worker; no invented credentials. */
export const REPOSITORY_URL = "https://github.com/donkizzy/law-padi"
/** Public contact address for corrections and privacy requests. */
export const CONTACT_EMAIL = "hello@amosgodwin.com"
export const CORRECTIONS_URL = `mailto:${CONTACT_EMAIL}?subject=Correction`
export const CORRECTIONS_LABEL = pages.links.corrections
export const SITE_DESCRIPTION =
  "Explore Nigeria's Constitution and published laws with precise citations, source-edition notices and original documents. Free and independent."
export const EDITION_CAVEAT = edition.constitutionNote.replace(
  "{{year}}",
  "2004",
)

// Page wording lives in the English `pages` catalogue; the Worker reads it here.
const withCaveat = (sections: readonly { heading: string; text: string }[]) =>
  sections.map((section) => ({
    ...section,
    text: section.text
      .replace("{{caveat}}", EDITION_CAVEAT)
      .replace("{{email}}", CONTACT_EMAIL),
  }))

export const publicPages = {
  "/about": {
    title: "About, sources and corrections | constitution.ng",
    description:
      "Who publishes constitution.ng, which source editions it uses, how sources and explanations are checked, and how to report a correction.",
    heading: pages.about.heading,
    sections: withCaveat(pages.about.sections),
  },
  "/methodology": {
    title: "Retrieval test and methodology | constitution.ng",
    description:
      "Read the scope and limits of constitution.ng's dated plain-language retrieval benchmark, including the test set and source edition.",
    heading: pages.methodology.heading,
    sections: withCaveat(pages.methodology.sections),
  },
} as const

export type SeoMetadata = {
  title: string
  description: string
  canonical?: string
  index?: boolean
  schema?: Record<string, unknown>[]
}

/** Validates the configured canonical origin: a bare HTTPS origin or an error. */
export function siteOrigin(value: string): string {
  const url = new URL(value)
  if (
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    url.port ||
    url.pathname !== "/" ||
    url.search ||
    url.hash
  )
    throw new Error("Public site URL must be a bare HTTPS origin")
  return url.origin
}

export function referencePath(path: string, release: string) {
  return `/laws/${encodeURIComponent(path.split(".")[0])}/${encodeURIComponent(path)}?${new URLSearchParams({ release })}`
}

export function browsePath(
  parent?: string,
  release?: string,
  instrument = parent?.split(".")[0] || "constitution-1999",
) {
  const query = new URLSearchParams()
  if (parent) query.set("parent", parent)
  if (release) query.set("release", release)
  return `/laws/${encodeURIComponent(instrument)}${query.size ? `?${query}` : ""}`
}

export function websiteSchema(origin: string) {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${origin}/#website`,
    url: `${origin}/welcome`,
    name: "constitution.ng",
    description: SITE_DESCRIPTION,
    inLanguage: "en",
    publisher: {
      "@type": "Organization",
      "@id": `${origin}/#publisher`,
      name: "constitution.ng",
      url: `${origin}/about`,
    },
  }
}

export function pageSchema(
  title: string,
  canonical: string,
  description: string,
) {
  return {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "@id": canonical,
    url: canonical,
    name: title,
    description,
    inLanguage: "en",
    isPartOf: { "@id": `${new URL(canonical).origin}/#website` },
  }
}

export function seoHead(metadata: SeoMetadata) {
  return {
    meta: [
      { title: metadata.title },
      { name: "description", content: metadata.description },
      {
        name: "robots",
        content: metadata.index ? "index, follow" : "noindex, follow",
      },
      { property: "og:type", content: "website" },
      { property: "og:site_name", content: "constitution.ng" },
      { property: "og:title", content: metadata.title },
      { property: "og:description", content: metadata.description },
      ...(metadata.canonical
        ? [{ property: "og:url", content: metadata.canonical }]
        : []),
      { name: "twitter:card", content: "summary" },
    ],
    links: metadata.canonical
      ? [{ rel: "canonical", href: metadata.canonical }]
      : [],
    scripts: (metadata.schema ?? []).map((schema) => ({
      type: "application/ld+json",
      children: JSON.stringify(schema).replace(/</g, "\\u003c"),
    })),
  }
}

export function provisionMetadata(
  provision: {
    citation: string
    title?: string | null
    canonical_path: string
    release_version: string
    edition_label?: string | null
    instrument_slug?: string
    instrument_title?: string
    instrument_short_title?: string | null
    ancestors?: {
      canonical_path: string
      citation: string
      has_text: boolean
    }[]
  },
  origin: string,
): SeoMetadata {
  const years = provision.edition_label?.match(/\b(?:19|20)\d{2}\b/g)
  const slug =
    provision.instrument_slug || provision.canonical_path.split(".")[0]
  const constitution = slug === "constitution-1999"
  const law = constitution
    ? "Nigeria's Constitution"
    : provision.instrument_short_title || provision.instrument_title || slug
  const edition = !constitution
    ? "as-enacted edition"
    : years?.length
      ? `${years[years.length - 1]} source edition`
      : "source edition"
  const title = `${provision.citation}${provision.title ? `: ${provision.title}` : ""} | ${edition} | constitution.ng`
  const canonical = `${origin}${referencePath(provision.canonical_path, provision.release_version)}`
  const description = `Read ${provision.citation}${provision.title ? ` (${provision.title})` : ""} in ${law}, ${edition}, with its citation and original source. Later amendments may differ.`
  return {
    title,
    description,
    canonical,
    index: true,
    schema: [
      websiteSchema(origin),
      pageSchema(title, canonical, description),
      {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        itemListElement: [
          {
            name: `Browse ${law}`,
            item:
              origin + browsePath(undefined, provision.release_version, slug),
          },
          ...(provision.ancestors ?? []).map((node) => ({
            name: node.citation,
            item:
              origin +
              (node.has_text
                ? referencePath(node.canonical_path, provision.release_version)
                : browsePath(node.canonical_path, provision.release_version)),
          })),
          { name: provision.citation, item: canonical },
        ].map((node, index) => ({
          "@type": "ListItem",
          position: index + 1,
          ...node,
        })),
      },
    ],
  }
}
