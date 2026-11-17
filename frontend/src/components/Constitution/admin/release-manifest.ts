import type { CorpusReleaseManifestPublic } from "@/client"

type ReleaseManifestSourcePreview = {
  authority?: string
  id?: string
  pageCountLabel?: string
  title?: string
}

type ReleaseManifestEntryPreview = {
  canonicalPath?: string
  id?: string
  pageRange?: string
}

export function releaseManifestSummary(
  manifest?: CorpusReleaseManifestPublic,
): {
  entryCount?: number
  entries: ReleaseManifestEntryPreview[]
  sourceCount?: number
  sources: ReleaseManifestSourcePreview[]
} {
  const manifestBody = manifest?.manifest
  if (!manifestBody || typeof manifestBody !== "object") {
    return { entries: [], sources: [] }
  }
  const sourceDocuments = Array.isArray(manifestBody.source_documents)
    ? manifestBody.source_documents
    : []
  const entries = Array.isArray(manifestBody.entries)
    ? manifestBody.entries
    : []
  return {
    entryCount: entries.length,
    entries: entries
      .slice(0, 4)
      .map((entry) => releaseManifestEntryPreview(entry)),
    sourceCount: sourceDocuments.length,
    sources: sourceDocuments
      .slice(0, 3)
      .map((source) => releaseManifestSourcePreview(source)),
  }
}

function releaseManifestSourcePreview(
  value: unknown,
): ReleaseManifestSourcePreview {
  if (!value || typeof value !== "object") return {}
  const source = value as Record<string, unknown>
  const pageCount =
    typeof source.page_count === "number"
      ? `${source.page_count} pages`
      : undefined
  return {
    authority:
      typeof source.authority === "string" ? source.authority : undefined,
    // Single-run manifests key a source by `source_document_id`; composed
    // releases also write `id`.
    id:
      typeof source.id === "string"
        ? source.id
        : typeof source.source_document_id === "string"
          ? source.source_document_id
          : undefined,
    pageCountLabel: pageCount,
    title: typeof source.title === "string" ? source.title : undefined,
  }
}

function releaseManifestEntryPreview(
  value: unknown,
): ReleaseManifestEntryPreview {
  if (!value || typeof value !== "object") return {}
  const entry = value as Record<string, unknown>
  const pageStart =
    typeof entry.source_page_start === "number"
      ? entry.source_page_start
      : undefined
  const pageEnd =
    typeof entry.source_page_end === "number"
      ? entry.source_page_end
      : pageStart
  return {
    canonicalPath:
      typeof entry.canonical_path === "string"
        ? entry.canonical_path
        : undefined,
    id:
      typeof entry.provision_version_id === "string"
        ? entry.provision_version_id
        : undefined,
    pageRange:
      pageStart !== undefined && pageEnd !== undefined
        ? `Source pages ${pageStart}${pageEnd === pageStart ? "" : `-${pageEnd}`}`
        : undefined,
  }
}
