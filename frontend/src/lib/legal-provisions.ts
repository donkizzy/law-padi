import type { LegalSearchResult } from "@/client"

export function provisionUrl(provision: LegalSearchResult) {
  return `${window.location.origin}/constitution/${encodeURIComponent(provision.canonical_path)}?release=${encodeURIComponent(provision.release_version)}`
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
export function editionName(label: string | null | undefined) {
  const year = editionYear(label)
  return year ? `1999 Constitution (${year} edition)` : "1999 Constitution"
}

/** One plain sentence about what the edition does and doesn't include. */
export function editionNote(label: string | null | undefined) {
  const year = editionYear(label)
  return year
    ? `This is the 1999 Constitution as published in ${year}. Later amendments aren't included yet, so a section may have changed since.`
    : "Later amendments to the Constitution aren't included yet, so a section may have changed since."
}

/** Short badge text for a provision's legal status. */
export function statusLabel(status: string, label: string | null | undefined) {
  if (status === "historical") {
    const year = editionYear(label)
    return year ? `${year} edition` : "Earlier edition"
  }
  if (status === "proposed") return "Proposed change"
  return status === "current" ? "Current" : status.replace(/_/g, " ")
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
    ? `page ${provision.source_page_start}${provision.source_page_end && provision.source_page_end !== provision.source_page_start ? `–${provision.source_page_end}` : ""}`
    : "page not recorded"
  return `${provision.citation}${provision.title ? ` — ${provision.title}` : ""}\n${provision.authoritative_text}\n\n${editionName(provision.edition_label)}, ${provision.source_authority}, ${pages}\n${provision.legal_status === "historical" ? `${editionNote(provision.edition_label)}\n` : ""}${provisionUrl(provision)}`
}
