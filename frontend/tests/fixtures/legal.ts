import type {
  LegalInstrumentPublic,
  LegalInstrumentsPublic,
  LegalReleasePublic,
  LegalSearchResponse,
  LegalSearchResult,
  ProvisionReference,
  ProvisionTreePublic,
} from "../../src/client"

// Bodies of the legal corpus endpoints, typed against the generated client.

export const constitutionEdition =
  "Historical/source Constitution compilation (LFN 2004)"

export function currentRelease(
  overrides: Partial<LegalReleasePublic> = {},
): LegalReleasePublic {
  return {
    release_id: "55555555-5555-4555-8555-555555555555",
    release_version: "published-test",
    index_kind: "enacted",
    embedding_run_id: "33333333-3333-4333-8333-333333333333",
    retrieval_index_build_id: "44444444-4444-4444-8444-444444444444",
    edition_label: constitutionEdition,
    available: true,
    legal_statuses: ["historical"],
    ...overrides,
  }
}

export function legalInstrument(
  overrides: Partial<LegalInstrumentPublic> = {},
): LegalInstrumentPublic {
  return {
    slug: "constitution-1999",
    title: "Constitution of the Federal Republic of Nigeria 1999",
    short_title: "1999 Constitution",
    instrument_type: "constitution",
    edition_label: constitutionEdition,
    edition_note: "Later amendments aren't included yet.",
    section_count: 320,
    legal_statuses: ["historical"],
    ...overrides,
  }
}

export function legalInstruments(
  data: LegalInstrumentPublic[],
  releaseVersion = "published-test",
): LegalInstrumentsPublic {
  return { data, count: data.length, release_version: releaseVersion }
}

export function provisionReference(
  overrides: Partial<ProvisionReference> = {},
): ProvisionReference {
  const canonical_path =
    overrides.canonical_path ?? "constitution-1999.chapter4.section37"
  return {
    id: canonical_path,
    canonical_path,
    kind: "section",
    number: null,
    heading: null,
    title: null,
    citation: "Section 37",
    has_text: true,
    authoritative_text: null,
    ...overrides,
  }
}

export function legalSearchResult(
  overrides: Partial<LegalSearchResult> = {},
): LegalSearchResult {
  const sourceDocumentId = "22222222-2222-4222-8222-222222222222"
  const releaseVersion = overrides.release_version ?? "published-test"
  return {
    canonical_path: "constitution-1999.chapter4.section37",
    citation: "Section 37",
    heading: "Right to private and family life",
    ancestor_headings: [],
    authoritative_text:
      "The privacy of citizens, their homes, correspondence, telephone conversations and telegraphic communications is hereby guaranteed and protected.",
    source_document_id: sourceDocumentId,
    source_page_start: 39,
    source_page_end: 39,
    legal_status: "historical",
    release_version: releaseVersion,
    dense_rank: null,
    lexical_rank: null,
    hybrid_score: 1,
    provision_id: "33333333-3333-4333-8333-333333333333",
    provision_version_id: "44444444-4444-4444-8444-444444444444",
    release_id: "55555555-5555-4555-8555-555555555555",
    kind: "section",
    edition_label: constitutionEdition,
    source_title: "Constitution compilation",
    source_authority: "Retained source authority",
    source_url: "https://example.test/constitution.pdf",
    source_content_url: `/api/v1/legal/sources/${sourceDocumentId}/content?release_version=${releaseVersion}`,
    ancestors: [],
    children: [],
    ...overrides,
  }
}

export function legalSearchResponse(
  overrides: Partial<LegalSearchResponse> = {},
): LegalSearchResponse {
  const data = overrides.data ?? [legalSearchResult()]
  return {
    data,
    count: data.length,
    outcome: "exact",
    retrieval_mode: "exact",
    message: null,
    release_version: "published-test",
    edition_label: constitutionEdition,
    ...overrides,
  }
}

export function provisionTree(
  overrides: Partial<ProvisionTreePublic> = {},
): ProvisionTreePublic {
  const data = overrides.data ?? []
  return {
    data,
    count: data.length,
    parent: null,
    scope: "children",
    release_version: "published-test",
    edition_label: constitutionEdition,
    ...overrides,
  }
}
