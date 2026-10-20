import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
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
  const { t } = useTranslation("chat")
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
      aria-label={t("feedback.label")}
      className="mt-3 flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
    >
      <span>{t("feedback.question")}</span>
      <InlineAction
        type="button"
        aria-pressed={rating === true}
        disabled={saving}
        onClick={() => void rate(true)}
      >
        {t("feedback.helpful")}
      </InlineAction>
      <InlineAction
        type="button"
        aria-pressed={rating === false}
        disabled={saving}
        onClick={() => void rate(false)}
      >
        {t("feedback.notHelpful")}
      </InlineAction>
      {rating !== null && <span role="status">{t("feedback.thanks")}</span>}
      {error && <span role="alert">{t("feedback.failed")}</span>}
    </fieldset>
  )
}
