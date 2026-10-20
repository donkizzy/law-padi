import type { LegalSearchResult } from "@/client"
import english from "../locales/en/edition.json"
import { referencePath } from "./seo"

export type EditionKey = keyof typeof english
type Translate = (key: EditionKey, values?: Record<string, string>) => string

// English unless the browser installs its catalogue; the Worker stays English.
let say: Translate = (key, values = {}) =>
  english[key].replace(/\{\{(\w+)\}\}/g, (_, name) => values[name] ?? "")

export function setEditionTranslator(translate: Translate) {
  say = translate
}

/** "page 12" or "page 12–13" in the reader's language. */
export function pageLabel(pages: string | number) {
  return say("page", { pages: String(pages) })
}

export type InstrumentContext = {
  instrument_slug?: string
  instrument_title?: string
  instrument_short_title?: string | null
  canonical_path?: string
}

export function instrumentSlug(context?: InstrumentContext | string) {
  return typeof context === "string"
    ? context
    : context?.instrument_slug ||
        context?.canonical_path?.split(".")[0] ||
        "constitution-1999"
}

export function lawName(context?: InstrumentContext | string) {
  const slug = instrumentSlug(context)
  if (slug === "constitution-1999") return say("constitution")
  if (
    typeof context !== "string" &&
    (context?.instrument_short_title || context?.instrument_title)
  )
    return context.instrument_short_title || context.instrument_title || slug
  return (
    (
      {
        "acja-2015": "ACJA 2015",
        "police-act-2020": "Police Act 2020",
      } as Record<string, string>
    )[slug] || slug
  )
}

export function shortCitation(
  source: InstrumentContext & {
    citation: string
    short_citation?: string | null
  },
) {
  return source.short_citation || source.citation
}

/** Find and Browse treat a bare number as a section reference. */
export function sectionQuery(query: string) {
  const value = query.trim()
  return /^\d+[a-z]?(?:\(\d+[a-z]?\))?(?:\([a-z]\))?$/i.test(value)
    ? `Section ${value}`
    : value
}

export function provisionUrl(provision: LegalSearchResult) {
  return `${window.location.origin}${referencePath(provision.canonical_path, provision.release_version)}`
}

export function sourceUrl(provision: LegalSearchResult) {
  const base = import.meta.env.VITE_API_URL || window.location.origin
  const url = new URL(provision.source_content_url, base)
  if (provision.source_page_start)
    url.hash = `page=${provision.source_page_start}`
  return url.href
}

function editionYear(label: string | null | undefined) {
  const years = label?.match(/\b(?:19|20)\d{2}\b/g)
  return years?.[years.length - 1]
}

/** "1999 Constitution (2004 edition)" from the release's edition label. */
export function editionName(
  label: string | null | undefined,
  context?: InstrumentContext | string,
) {
  if (instrumentSlug(context) !== "constitution-1999")
    return say("lawAsEnacted", { law: lawName(context) })
  if (/as enacted/i.test(label || "")) return say("asEnacted")
  const year = editionYear(label)
  return year ? say("constitutionEdition", { year }) : say("constitutionName")
}

/** A release can combine several source editions. */
export function releaseEditionName(label: string | null | undefined) {
  return /constitution|LFN/i.test(label || "")
    ? editionName(label)
    : label || say("publishedEditions")
}

/** One plain sentence about what the edition does and doesn't include. */
export function editionNote(
  label: string | null | undefined,
  context?: InstrumentContext | string,
) {
  if (instrumentSlug(context) !== "constitution-1999")
    return say("lawNote", { law: lawName(context) })
  if (/as enacted/i.test(label || "")) return say("asEnactedNote")
  const year = editionYear(label)
  return year
    ? say("constitutionNote", { year })
    : say("constitutionNoteUndated")
}

/** Short badge text for a provision's legal status. */
export function statusLabel(
  status: string,
  label: string | null | undefined,
  context?: InstrumentContext | string,
) {
  if (status === "historical") {
    if (
      instrumentSlug(context) !== "constitution-1999" ||
      /as enacted/i.test(label || "")
    )
      return say("asEnacted")
    const year = editionYear(label)
    return year ? say("yearEdition", { year }) : say("earlierEdition")
  }
  if (status === "proposed") return say("proposed")
  return status === "current" ? say("current") : status.replace(/_/g, " ")
}

/**
 * Join the source PDF's line wraps for reading, keeping real breaks before
 * numbered parts such as (1), (a) or (iv) and before provisos. Display only:
 * copied and stored text stay exactly as published.
 */
export function readableText(text: string) {
  return text
    .replace(/[ \t]+\n/g, "\n")
    .replace(
      /\n(?!\s*(?:\((?:\d+[a-z]?|[a-z]{1,2}|[ivxlc]+)\)|Provided\b))\s*/g,
      " ",
    )
    .replace(/([;:\u2014-])\s+(\((?:\d+[a-z]?|[a-z]|[ivxlc]+)\)\s)/g, "$1\n$2")
    .replace(/^\n/, "")
}

/** Section title for display, falling back to the citation. */
export function provisionTitle(provision: {
  title?: string | null
  citation: string
}) {
  return provision.title || provision.citation
}

export function copyText(provision: LegalSearchResult) {
  const pages = provision.source_page_start
    ? pageLabel(
        `${provision.source_page_start}${provision.source_page_end && provision.source_page_end !== provision.source_page_start ? `–${provision.source_page_end}` : ""}`,
      )
    : say("pageNotRecorded")
  return `${provision.citation}${provision.title ? ` — ${provision.title}` : ""}\n${provision.authoritative_text}\n\n${editionName(provision.edition_label, provision)}, ${provision.source_authority}, ${pages}\n${provision.legal_status === "historical" ? `${editionNote(provision.edition_label, provision)}\n` : ""}${provisionUrl(provision)}`
}
