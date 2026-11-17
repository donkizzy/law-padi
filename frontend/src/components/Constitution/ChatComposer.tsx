import { type RefObject, useEffect, useId, useRef } from "react"
import { useTranslation } from "react-i18next"
import { FiArrowUp, FiBookOpen, FiSearch } from "react-icons/fi"

import { SquircleButton } from "@/components/Constitution/primitives"
import { useWorkspacePreferences } from "@/hooks/useWorkspacePreferences"
import { intlLocales } from "@/lib/i18n"
import { cn } from "@/lib/utils"

type ChatComposerProps = {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  placeholder?: string
  compact?: boolean
  contextLabel?: string
  loading?: boolean
  disabled?: boolean
  className?: string
  purpose?: "search" | "explanation"
  inputRef?: RefObject<HTMLTextAreaElement | null>
  autoFocus?: boolean
}

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  placeholder,
  compact = false,
  contextLabel,
  loading = false,
  disabled = false,
  className,
  purpose = "search",
  inputRef,
  autoFocus = false,
}: ChatComposerProps) {
  const { t, i18n } = useTranslation("chat")
  const count = new Intl.NumberFormat(intlLocales(i18n.resolvedLanguage))
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const hintId = useId()
  const { preferences } = useWorkspacePreferences()

  useEffect(() => {
    if (!autoFocus) return
    const frame = requestAnimationFrame(() =>
      textareaRef.current?.focus({ preventScroll: true }),
    )
    return () => cancelAnimationFrame(frame)
  }, [autoFocus])

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    textarea.style.height = value.length ? "0px" : "auto"
    textarea.style.height = `${Math.min(textarea.scrollHeight, compact ? 140 : 220)}px`
  }, [compact, value])

  const submit = () => {
    if (disabled || loading || !value.trim()) return
    onSubmit()
  }

  return (
    <div
      className={cn(
        "sq-lg border border-border bg-card p-3 shadow-[var(--shadow-subtle)] transition-[border-color,box-shadow] duration-200 sm:p-3.5",
        "focus-within:border-primary/35 focus-within:ring-[3px] focus-within:ring-ring/10",
        disabled && "opacity-60",
        className,
      )}
    >
      <textarea
        data-chat-composer
        aria-label={t("composer.label")}
        aria-describedby={hintId}
        className={cn(
          "block w-full resize-none bg-transparent px-2 py-2 text-body-lg text-foreground outline-none [overflow-wrap:anywhere]",
          "placeholder:text-muted-foreground",
          compact ? "min-h-11" : "min-h-24",
        )}
        disabled={disabled}
        maxLength={2000}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (
            event.nativeEvent.isComposing ||
            event.nativeEvent.keyCode === 229
          )
            return
          if (
            event.key === "Enter" &&
            !event.shiftKey &&
            (preferences.enterToSend || event.metaKey || event.ctrlKey)
          ) {
            event.preventDefault()
            submit()
          }
        }}
        placeholder={placeholder ?? t("composer.placeholder")}
        ref={(element) => {
          textareaRef.current = element
          if (inputRef) inputRef.current = element
        }}
        value={value}
      />

      <div className="mt-2 flex items-end justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 self-center px-2">
          <span className="inline-flex max-w-full items-center gap-2 py-1 text-label font-medium text-muted-foreground [overflow-wrap:anywhere]">
            {purpose === "explanation" ? (
              <FiBookOpen className="size-4 shrink-0" aria-hidden />
            ) : (
              <FiSearch className="size-4 shrink-0" aria-hidden />
            )}
            <span>
              {purpose === "explanation"
                ? t("composer.explanation")
                : t("composer.search")}
            </span>
          </span>
          {contextLabel ? (
            <span className="text-label font-normal text-muted-foreground [overflow-wrap:anywhere]">
              {contextLabel}
            </span>
          ) : null}
        </div>

        <SquircleButton
          aria-label={loading ? t("composer.sending") : t("composer.send")}
          className="sq-sm size-11 shrink-0 px-0 shadow-none enabled:active:scale-95 disabled:border-border disabled:bg-secondary disabled:text-muted-foreground disabled:opacity-100"
          disabled={!value.trim() || disabled || value.length > 2000}
          loading={loading}
          onClick={submit}
          type="button"
        >
          {loading ? (
            <span className="sr-only">{t("composer.sending")}</span>
          ) : (
            <FiArrowUp className="size-5" strokeWidth={2.4} aria-hidden />
          )}
        </SquircleButton>
      </div>
      <div
        id={hintId}
        className="mt-2 flex justify-between gap-3 px-2 text-label font-normal text-muted-foreground"
      >
        <span>
          {preferences.enterToSend
            ? t("composer.enterHint")
            : t("composer.modEnterHint")}
        </span>
        <span
          className="shrink-0 tabular-nums"
          aria-live={value.length >= 1900 ? "polite" : "off"}
        >
          {count.format(value.length)}/{count.format(2000)}
        </span>
      </div>
    </div>
  )
}
