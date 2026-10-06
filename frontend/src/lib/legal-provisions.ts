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

export function copyText(provision: LegalSearchResult) {
  const pages = provision.source_page_start
    ? `PDF page ${provision.source_page_start}${provision.source_page_end && provision.source_page_end !== provision.source_page_start ? `–${provision.source_page_end}` : ""}`
    : "Page not recorded"
  return `${provision.citation}\n${provision.authoritative_text}\n\n${provision.edition_label} (${provision.legal_status})\n${provision.source_title}\n${provision.source_authority}, ${pages}\n${provisionUrl(provision)}`
}
