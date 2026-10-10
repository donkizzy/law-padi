import { useInfiniteQuery } from "@tanstack/react-query"
import { ConversationsService } from "@/client"

export function conversationHeaders(): Record<string, string> {
  const token = localStorage.getItem("access_token")
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function useConversations() {
  return useInfiniteQuery({
    queryKey: ["conversations"],
    initialPageParam: 0,
    queryFn: async ({ signal, pageParam }) =>
      (
        await ConversationsService.listConversations({
          query: { offset: pageParam, limit: 30 },
          headers: conversationHeaders(),
          withCredentials: true,
          signal,
        })
      ).data,
    getNextPageParam: (lastPage, pages) => {
      const loaded = pages.reduce((total, page) => total + page.data.length, 0)
      return loaded < lastPage.count ? loaded : undefined
    },
    retry: false,
    retryOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 10_000,
  })
}
