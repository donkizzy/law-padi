import { type RefObject, useEffect, useId, useRef } from "react"
import { FiSend } from "react-icons/fi"

import { SquircleButton } from "@/components/LawPadi/primitives"
import { useWorkspacePreferences } from "@/hooks/useWorkspacePreferences"
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
  placeholder = "Ask anything about Nigeria's Constitution…",
  compact = false,
  contextLabel,
  loading = false,
  disabled = false,
  className,
  purpose = "search",
  inputRef,
  autoFocus = false,
}: ChatComposerProps) {
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
        "sq-lg border border-input bg-card p-3 shadow-[var(--shadow-subtle)] transition",
        "focus-within:border-primary/35 focus-within:ring-[3px] focus-within:ring-ring/15",
        disabled && "opacity-60",
        className,
      )}
    >
      <textarea
        data-chat-composer
        aria-label="Your question"
        aria-describedby={hintId}
        className={cn(
          "block w-full resize-none bg-transparent px-1 text-[0.98rem] leading-7 text-foreground outline-none",
          "placeholder:text-muted-foreground",
          compact ? "min-h-16" : "min-h-24",
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
        placeholder={placeholder}
        ref={(element) => {
          textareaRef.current = element
          if (inputRef) inputRef.current = element
        }}
        value={value}
      />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="sq-sm bg-secondary px-3 py-2 text-label text-muted-foreground">
            {purpose === "explanation"
              ? "Answers in plain English"
              : "Search the Constitution"}
          </span>
          {contextLabel ? (
            <span className="text-label font-normal text-muted-foreground">
              {contextLabel}
            </span>
          ) : null}
        </div>

        <SquircleButton
          aria-label={loading ? "Sending" : "Send question"}
          className="min-w-11 px-0"
          disabled={!value.trim() || disabled || value.length > 2000}
          loading={loading}
          onClick={submit}
          type="button"
        >
          {loading ? (
            <span className="sr-only">Sending</span>
          ) : (
            <FiSend className="size-4" aria-hidden />
          )}
        </SquircleButton>
      </div>
      <div
        id={hintId}
        className="mt-2 flex justify-between gap-3 px-1 text-xs text-muted-foreground"
      >
        <span>
          {preferences.enterToSend
            ? "Enter to send · Shift+Enter for a new line"
            : "Ctrl/Cmd+Enter to send"}
        </span>
        <span aria-live={value.length >= 1900 ? "polite" : "off"}>
          {value.length}/2,000
        </span>
      </div>
    </div>
  )
}
