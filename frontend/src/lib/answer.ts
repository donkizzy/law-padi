import { z } from "zod"
import type {
  CitationOutcome,
  EvidenceItem,
  InstrumentType,
  ProvisionNotice,
} from "@/client"

// The answer a conversation stores and streams. The OpenAPI schema types it as
// a free-form object, so the shape the screens rely on is declared here and
// checked at the boundary: data that does not match is reported as unreadable
// instead of reaching a component that would throw while rendering.
// Mirrors `ExplanationAnswer` in `backend/app/chat/schemas.py`.

export type AnswerBlock = {
  text: string
  evidence_ids: string[]
  quotation?: string | null
}

export type AnswerTranslation = {
  language: string
  blocks: AnswerBlock[]
  missing_facts: string[]
  follow_up_questions: string[]
}

export type ExplanationAnswer = {
  outcome: string
  blocks: AnswerBlock[]
  missing_facts: string[]
  follow_up_questions?: string[]
  citation_outcomes: CitationOutcome[]
  evidence: EvidenceItem[]
  related_laws?: string[]
  notice?: string | null
  notice_code?: string | null
  notice_params?: { laws?: string[]; choices?: string[] }
  question_language?: string | null
  answer_language?: string
  translation?: AnswerTranslation | null
}

const strings = z.array(z.string())

// The statuses the API publishes (`LegalStatus` in `backend/app/legal/enums.py`).
const legalStatus = z.enum([
  "current",
  "superseded",
  "repealed",
  "proposed",
  "historical",
])

const instrumentType: z.ZodType<InstrumentType> = z.enum([
  "constitution",
  "alteration_act",
  "bill",
  "act",
  "regulation",
])

const notice: z.ZodType<ProvisionNotice> = z.looseObject({
  code: z.string(),
  text: z.string(),
  params: z.record(z.string(), z.string()).optional(),
})

const evidenceItem: z.ZodType<EvidenceItem> = z.looseObject({
  instrument_slug: z.string().optional(),
  instrument_title: z.string().optional(),
  instrument_short_title: z.string().nullish(),
  instrument_type: instrumentType.optional(),
  short_citation: z.string().nullish(),
  evidence_id: z.string(),
  provision_id: z.string(),
  provision_version_id: z.string(),
  canonical_path: z.string(),
  citation: z.string(),
  title: z.string().nullish(),
  authoritative_text: z.string(),
  text_sha256: z.string(),
  ancestor_citations: strings,
  legal_status: legalStatus,
  edition_label: z.string(),
  release_id: z.string(),
  release_version: z.string(),
  source_document_id: z.string(),
  source_title: z.string(),
  source_authority: z.string(),
  source_url: z.string(),
  source_content_url: z.string(),
  source_page_start: z.number().nullish(),
  source_page_end: z.number().nullish(),
  notices: z.array(notice).optional(),
})

const citationOutcome: z.ZodType<CitationOutcome> = z.looseObject({
  reference: z.string(),
  status: z.enum(["resolved", "ambiguous", "missing", "unsupported"]),
  evidence_ids: strings.optional(),
  message: z.string().nullish(),
})

const block: z.ZodType<AnswerBlock> = z.looseObject({
  text: z.string(),
  evidence_ids: strings.default([]),
  quotation: z.string().nullish(),
})

const translation: z.ZodType<AnswerTranslation> = z.looseObject({
  language: z.string(),
  blocks: z.array(block).default([]),
  missing_facts: strings.default([]),
  follow_up_questions: strings.default([]),
})

// Lists the server omits default to empty, as the server defaults them, so an
// answer stored before a field existed still reads.
const answer: z.ZodType<ExplanationAnswer> = z.looseObject({
  outcome: z.string(),
  blocks: z.array(block).default([]),
  missing_facts: strings.default([]),
  follow_up_questions: strings.optional(),
  citation_outcomes: z.array(citationOutcome).default([]),
  evidence: z.array(evidenceItem).default([]),
  related_laws: strings.optional(),
  notice: z.string().nullish(),
  notice_code: z.string().nullish(),
  notice_params: z
    .looseObject({ laws: strings.optional(), choices: strings.optional() })
    .optional(),
  question_language: z.string().nullish(),
  answer_language: z.string().optional(),
  translation: translation.nullish(),
})

const evidenceList = z.array(evidenceItem)
const citationOutcomeList = z.array(citationOutcome)

/** The answer, or null when the data is not an answer the screens can show. */
export function parseAnswer(value: unknown): ExplanationAnswer | null {
  const result = answer.safeParse(value)
  return result.success ? result.data : null
}

/** The evidence of a streamed event, or null when it is malformed. */
export function parseEvidence(value: unknown): EvidenceItem[] | null {
  const result = evidenceList.safeParse(value)
  return result.success ? result.data : null
}

/** The citation outcomes of a streamed event, or null when malformed. */
export function parseCitationOutcomes(
  value: unknown,
): CitationOutcome[] | null {
  const result = citationOutcomeList.safeParse(value)
  return result.success ? result.data : null
}
