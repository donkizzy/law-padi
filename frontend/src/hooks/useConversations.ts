import { useInfiniteQuery } from "@tanstack/react-query"
import { ConversationsService } from "@/client"
import { getAccessToken } from "@/lib/session"
import { useChatCapabilities } from "./useChatCapabilities"

export function conversationHeaders(): Record<string, string> {
  const token = getAccessToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function useConversations(query = "") {
  const capabilities = useChatCapabilities()
  return useInfiniteQuery({
    queryKey: ["conversations", query],
    initialPageParam: 0,
    enabled: capabilities.data?.conversations_enabled === true,
    queryFn: async ({ signal, pageParam }) =>
      (
        await ConversationsService.listConversations({
          query: { offset: pageParam, limit: 30, q: query || undefined },
          headers: conversationHeaders(),
          withCredentials: true,
          signal,
        })
      ).data,
    getNextPageParam: (lastPage, pages) => {
      const loaded = pages.reduce((total, page) => total + page.data.length, 0)
      return loaded < lastPage.count ? loaded : undefined
    },
    retry: 1,
    retryOnMount: true,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    staleTime: 10_000,
  })
}
