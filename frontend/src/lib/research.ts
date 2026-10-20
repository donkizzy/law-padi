import {
  type ConversationDetail,
  ConversationsService,
  type EvidenceItem,
} from "@/client"
import { conversationHeaders } from "@/hooks/useConversations"
import { preferencesKey } from "@/hooks/useWorkspacePreferences"
import { editionName, editionNote } from "./legal-provisions"
import { referencePath } from "./seo"

export function evidenceUrl(
  item: Pick<EvidenceItem, "canonical_path" | "release_version">,
) {
  return `${window.location.origin}${referencePath(item.canonical_path, item.release_version)}`
}

export type CopySource = Partial<
  Pick<
    EvidenceItem,
    "instrument_slug" | "instrument_title" | "instrument_short_title"
  >
> &
  Pick<
    EvidenceItem,
    | "canonical_path"
    | "release_version"
    | "citation"
    | "title"
    | "authoritative_text"
    | "edition_label"
    | "legal_status"
    | "source_authority"
    | "source_title"
    | "source_page_start"
  >
export function evidenceCopy(item: CopySource) {
  return `${item.citation}${item.title ? ` — ${item.title}` : ""}\n${item.authoritative_text}\n\n${editionName(item.edition_label, item)}\n${item.legal_status === "historical" ? `${editionNote(item.edition_label, item)}\n` : ""}${item.source_authority} · ${item.source_title}${item.source_page_start ? ` · page ${item.source_page_start}` : ""}\n${evidenceUrl(item)}`
}

export function downloadResearch(name: string, data: unknown) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  )
  const link = document.createElement("a")
  link.href = url
  link.download = name
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export async function readCompleteConversation(
  id: string,
  signal?: AbortSignal,
): Promise<ConversationDetail> {
  const options = {
    path: { conversation_id: id },
    headers: conversationHeaders(),
    withCredentials: true,
    signal,
  }
  const { data } = await ConversationsService.readConversation(options)
  const messages = [...data.messages]
  const cursors = new Set<string>()
  let before = data.has_more_messages ? data.next_before : null
  while (before) {
    if (cursors.has(before))
      throw new Error(
        "Conversation history could not be fully exported. Try again.",
      )
    cursors.add(before)
    const page = await ConversationsService.readConversation({
      ...options,
      query: { before, limit: 100 },
    })
    messages.unshift(...page.data.messages)
    before = page.data.has_more_messages ? page.data.next_before : null
  }
  return { ...data, messages, has_more_messages: false, next_before: null }
}

export async function exportResearch(conversationsEnabled: boolean) {
  const conversations: ConversationDetail[] = []
  if (conversationsEnabled) {
    let offset = 0
    let count = 1
    while (offset < count) {
      const page = await ConversationsService.listConversations({
        query: { offset, limit: 100 },
        headers: conversationHeaders(),
        withCredentials: true,
      })
      count = page.data.count
      if (!page.data.data.length && offset < count)
        throw new Error(
          "Conversation history changed during export. Try again.",
        )
      for (const row of page.data.data)
        conversations.push(await readCompleteConversation(row.id))
      offset += page.data.data.length
    }
  }
  downloadResearch("constitution-ng-research.json", {
    format_version: 1,
    exported_at: new Date().toISOString(),
    availability: {
      conversations: conversationsEnabled ? "included" : "unavailable",
      bookmarks: "this browser",
      preferences: "this browser",
    },
    notice:
      "Source editions and linked provisions are retained. Explanations are not legal advice.",
    bookmarks: JSON.parse(
      localStorage.getItem("law-padi.saved-provisions.v1") ?? "[]",
    ),
    preferences: JSON.parse(localStorage.getItem(preferencesKey) ?? "{}"),
    conversations,
  })
}
