import type { CitationOutcome, EvidenceItem, Language } from "../../src/client"

// The answer the server stores in `MessagePublic.answer_content` and sends in
// the `answer.complete` stream event. The OpenAPI schema types that field as a
// free-form object, so this mirrors `ExplanationAnswer` in
// `backend/app/chat/schemas.py` by hand, built on the generated evidence and
// citation types.

export type ExplanationBlock = {
  text: string
  evidence_ids: string[]
  quotation: string | null
}

export type AnswerTranslation = {
  language: Language
  blocks: ExplanationBlock[]
  missing_facts: string[]
  follow_up_questions: string[]
  model: string
  prompt_version: string
  glossary_version: string | null
}

export type AnswerOutcome =
  | "completed"
  | "partial_evidence"
  | "insufficient_evidence"
  | "clarification_required"
  | "provider_failure"
  | "cancelled"
  | "capacity_exhausted"
  | "budget_exhausted"
  | "validation_failed"

export type ChatAnswer = {
  outcome: AnswerOutcome
  label: string
  blocks: ExplanationBlock[]
  missing_facts: string[]
  follow_up_questions: string[]
  citation_outcomes: CitationOutcome[]
  evidence: EvidenceItem[]
  related_laws: string[]
  notice: string | null
  notice_code: string | null
  notice_params: Record<string, unknown>
  question_language: Language | null
  answer_language: Language
  translation: AnswerTranslation | null
}

/** A completed English answer with every field the server always sends. */
export function chatAnswer(overrides: Partial<ChatAnswer> = {}): ChatAnswer {
  return {
    outcome: "completed",
    label: "Plain-language explanation",
    blocks: [],
    missing_facts: [],
    follow_up_questions: [],
    citation_outcomes: [],
    evidence: [],
    related_laws: [],
    notice: null,
    notice_code: null,
    notice_params: {},
    question_language: null,
    answer_language: "en",
    translation: null,
    ...overrides,
  }
}
