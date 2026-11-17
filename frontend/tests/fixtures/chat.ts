import type {
  ChatCapabilities,
  CitationOutcome,
  ConversationDetail,
  ConversationList,
  ConversationPublic,
  EvidenceItem,
  Language,
  MessageAccepted,
  MessagePublic,
} from "../../src/client"

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

// Bodies of the conversation endpoints, typed against the generated client so
// a renamed or newly required field fails the type-check instead of silently
// leaving the mocks behind.

/** Matches `EXPLANATION_PROMPT_VERSION` in `backend/app/chat/__init__.py`. */
export const explanationPromptVersion = "constitution-english-v11"

export function chatCapabilities(
  overrides: Partial<ChatCapabilities> = {},
): ChatCapabilities {
  return {
    conversations_enabled: true,
    explanations_enabled: true,
    supported_languages: ["English"],
    answer_languages: ["en"],
    question_max_length: 2000,
    build_revision: "test",
    prompt_version: explanationPromptVersion,
    ...overrides,
  }
}

export function conversationPublic(
  overrides: Partial<ConversationPublic> = {},
): ConversationPublic {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    title: "What does Section 37 protect?",
    release_version: "published-test",
    edition_label: "Historical/source Constitution compilation (LFN 2004)",
    created_at: "2026-10-08T08:00:00Z",
    updated_at: "2026-10-08T08:00:00Z",
    ...overrides,
  }
}

export function conversationList(
  data: ConversationPublic[] = [],
): ConversationList {
  return { data, count: data.length }
}

export function messagePublic(
  overrides: Partial<MessagePublic> = {},
): MessagePublic {
  return {
    id: "77777777-7777-4777-8777-777777777777",
    role: "user",
    content: "What does Section 37 protect?",
    answer_status: null,
    answer_content: null,
    evidence_snapshot: null,
    created_at: "2026-10-08T08:00:01Z",
    ...overrides,
  }
}

export function conversationDetail(
  overrides: Partial<ConversationDetail> = {},
): ConversationDetail {
  return {
    ...conversationPublic(),
    messages: [],
    active_run_id: null,
    ...overrides,
  }
}

export function messageAccepted(
  overrides: Partial<MessageAccepted> = {},
): MessageAccepted {
  return {
    run_id: "22222222-2222-4222-8222-222222222222",
    user_message_id: "77777777-7777-4777-8777-777777777777",
    status: "pending",
    ...overrides,
  }
}

// Server-sent events on `/conversations/{id}/events`. These are the events the
// worker emits that the page reads (`backend/app/chat/worker.py`), plus the
// `run.queued` event the endpoint derives while the run waits for the worker.
// That one is never stored, so it carries no ID.
export type ChatStreamEvent =
  | ({ id: number } & (
      | {
          event: "retrieval.complete"
          data: {
            evidence: EvidenceItem[]
            citation_outcomes: CitationOutcome[]
            retrieval_mode: "exact" | "hybrid" | "lexical" | null
            message: string | null
          }
        }
      | {
          event: "answer.complete"
          data: { message_id: string; answer: ChatAnswer }
        }
    ))
  | {
      id?: undefined
      event: "run.queued"
      /** `position` 1 means the run starts next. */
      data: { run_id: string; position: number }
    }

/** The `text/event-stream` body the server would send for these events. */
export function eventStreamBody(events: ChatStreamEvent[]): string {
  return events
    .map(
      ({ id, event, data }) =>
        `${id === undefined ? "" : `id: ${id}\n`}event: ${event}\ndata: ${JSON.stringify(data)}\n\n`,
    )
    .join("")
}
