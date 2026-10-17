/** Public identity shared by the browser and the Worker; no invented credentials. */
export const DEFAULT_SITE_URL =
  "https://constitition-ng.amosgodwin500.workers.dev"
export const REPOSITORY_URL = "https://github.com/donkizzy/law-padi"
export const CORRECTIONS_URL = `${REPOSITORY_URL}/issues`
export const SITE_DESCRIPTION =
  "Find sections of Nigeria's 1999 Constitution, read the 2004 source edition and check citations against the original document. Free and independent."
export const EDITION_CAVEAT =
  "This is the 1999 Constitution as published in 2004. Later amendments aren't included yet, so a section may have changed since."

export const publicPages = {
  "/about": {
    title: "About, sources and corrections | constitution.ng",
    description:
      "Who publishes constitution.ng, which Constitution edition it uses, how sources and explanations are checked, and how to report a correction.",
    heading: "About constitution.ng",
    sections: [
      {
        heading: "An independent constitutional reference",
        text: "constitution.ng publishes a searchable reading edition of Nigeria's Constitution and a tool for finding and explaining provisions. The publisher is constitution.ng. This is an independent project, not a government publication or a service affiliated with the National Assembly. Explanations are information, not legal advice.",
      },
      {
        heading: "Source edition and scope",
        text: `${EDITION_CAVEAT} The reading pages identify the exact release and link to the source document and printed page. The public corpus contains known source gaps, including a missing Section 168 and two Section 189 identities distinguished by their source locations. Do not assume this is a complete or current consolidated edition.`,
      },
      {
        heading: "How wording and explanations are handled",
        text: "The reading pages show published source wording separately from generated explanations. Citations come from structured provision identities. Explanations use retrieved evidence and automated checks, but can still miss context or details. This site does not certify every explanation as reviewed by a lawyer. Check the cited wording and source, and consult a qualified lawyer for a legal decision.",
      },
      {
        heading: "Updates and corrections",
        text: "A release identifies the edition being read; a new website build does not mean the law has changed. Corrections are tracked in the GitHub repository. Repository access is currently required; the link may be unavailable to signed-out visitors. When reporting an issue, include the provision link, release and printed page if available. Do not include private case details, contact information or confidential documents in a public issue.",
      },
    ],
  },
  "/methodology": {
    title: "Retrieval test and methodology | constitution.ng",
    description:
      "Read the scope and limits of constitution.ng's dated plain-language retrieval benchmark, including the test set and source edition.",
    heading: "How we check section retrieval",
    sections: [
      {
        heading: "What was measured",
        text: "The plain-language-retrieval-v1 benchmark contains 55 everyday English and Pidgin-style questions and expected sections. The recorded 12 October 2026 result reports a 0.98 top-one hit rate and 1.0 top-five hit rate after adding the topic guide. This is a retained retrieval result, not a new test of the current deployment.",
      },
      {
        heading: "What the result does not establish",
        text: "A retrieval hit means an expected section appeared in the measured search position. It does not measure the correctness of generated explanations, legal advice quality, completeness of the corpus, current-law coverage or performance on questions outside the test set. The questions are a small curated set, not a representative sample of all users.",
      },
      {
        heading: "Reproducible scope",
        text: "The versioned test file records each question and its expected sections. A repeat test should record the deployed revision, published corpus release, retrieval configuration, date and per-question results. Compare the same dataset before reporting a change. Source wording and later amendments require separate verification.",
      },
    ],
  },
} as const

export type SeoMetadata = {
  title: string
  description: string
  canonical?: string
  index?: boolean
  schema?: Record<string, unknown>[]
}

export function siteOrigin(value = DEFAULT_SITE_URL): string {
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
  return `/constitution/${encodeURIComponent(path)}?${new URLSearchParams({ release })}`
}

export function browsePath(parent?: string, release?: string) {
  const query = new URLSearchParams()
  if (parent) query.set("parent", parent)
  if (release) query.set("release", release)
  return `/constitution${query.size ? `?${query}` : ""}`
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
    ancestors?: {
      canonical_path: string
      citation: string
      has_text: boolean
    }[]
  },
  origin: string,
): SeoMetadata {
  const years = provision.edition_label?.match(/\b(?:19|20)\d{2}\b/g)
  const edition = years?.length
    ? `${years[years.length - 1]} source edition`
    : "source edition"
  const title = `${provision.citation}${provision.title ? `: ${provision.title}` : ""} | ${edition} | constitution.ng`
  const canonical = `${origin}${referencePath(provision.canonical_path, provision.release_version)}`
  const description = `Read ${provision.citation}${provision.title ? ` (${provision.title})` : ""} in Nigeria's Constitution, ${edition}, with its citation and original source. Later amendments may differ.`
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
            name: "Browse Constitution",
            item: origin + browsePath(undefined, provision.release_version),
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
