import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { ConversationsService, type MessagePublic } from "@/client"
import { useChatRequestScope } from "@/hooks/useChatRequestScope"
import { conversationHeaders } from "@/hooks/useConversations"
import { InlineAction } from "./primitives"

export function AnswerFeedback({
  message,
  conversationId,
}: {
  message: MessagePublic
  conversationId: string
}) {
  const [rating, setRating] = useState(message.helpful ?? null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(false)
  const beginRequest = useChatRequestScope()
  const queryClient = useQueryClient()
  useEffect(() => setRating(message.helpful ?? null), [message.helpful])
  const rate = async (helpful: boolean) => {
    const scope = beginRequest()
    setSaving(true)
    setError(false)
    try {
      await ConversationsService.submitMessageFeedback({
        path: { conversation_id: conversationId, message_id: message.id },
        body: { helpful },
        headers: conversationHeaders(),
        withCredentials: true,
        signal: scope.signal,
      })
      if (scope.current()) {
        setRating(helpful)
        void queryClient.invalidateQueries({
          queryKey: ["conversation", conversationId],
        })
      }
    } catch {
      if (scope.current()) setError(true)
    } finally {
      if (scope.current()) setSaving(false)
      scope.close()
    }
  }
  return (
    <fieldset
      aria-label="Answer feedback"
      className="mt-3 flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
    >
      <span>Was this useful?</span>
      <InlineAction
        type="button"
        aria-pressed={rating === true}
        disabled={saving}
        onClick={() => void rate(true)}
      >
        Helpful
      </InlineAction>
      <InlineAction
        type="button"
        aria-pressed={rating === false}
        disabled={saving}
        onClick={() => void rate(false)}
      >
        Not helpful
      </InlineAction>
      {rating !== null && <span role="status">Thanks for your feedback.</span>}
      {error && (
        <span role="alert">Feedback couldn't be saved. Try again.</span>
      )}
    </fieldset>
  )
}
