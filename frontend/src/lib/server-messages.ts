import i18n from "@/lib/i18n"

/**
 * Server messages are English. Outside English, a message with a known code
 * is shown from the chat catalogue; anything else stays as sent.
 */
export function serverMessage(
  message: string | null | undefined,
  code?: string | null,
): string | null {
  if (!message) return null
  const key = `chat:notices.${code}`
  if (!code || (i18n.resolvedLanguage ?? "en") === "en" || !i18n.exists(key))
    return message
  return i18n.t(key as "chat:notices.cancelled")
}
