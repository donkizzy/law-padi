import { useQuery } from "@tanstack/react-query"
import { ConversationsService } from "@/client"

export type ChatCapabilities = {
  conversations_enabled: boolean
  explanations_enabled: boolean
  supported_languages: string[]
  question_max_length: number
  build_revision: string
  prompt_version: string
}

export function useChatCapabilities() {
  return useQuery({
    queryKey: ["chat-capabilities"],
    queryFn: async ({ signal }) =>
      (await ConversationsService.readChatCapabilities({ signal })).data,
    staleTime: 30_000,
    retry: 1,
    refetchOnReconnect: true,
  })
}
