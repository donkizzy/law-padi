import { useQuery } from "@tanstack/react-query"
import { ConversationsService } from "@/client"

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
