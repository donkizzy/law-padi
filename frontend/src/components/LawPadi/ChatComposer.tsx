import { useEffect, useRef, useState } from "react"
import { FiPaperclip, FiSend } from "react-icons/fi"
import { LiaLanguageSolid } from "react-icons/lia"

import { IconButton, SquircleButton } from "@/components/LawPadi/primitives"
import { type LanguageValue, languageOptions } from "@/lib/law-padi-data"
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
}

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  placeholder = "Ask about the Nigerian Constitution...",
  compact = false,
  contextLabel,
  loading = false,
  disabled = false,
  className,
}: ChatComposerProps) {
  const [language, setLanguage] = useState<LanguageValue>("auto")
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    textarea.style.height = "0px"
    textarea.style.height = `${Math.min(textarea.scrollHeight, compact ? 140 : 220)}px`
  }, [compact])

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
        aria-label={contextLabel ?? "Your constitutional question"}
        className={cn(
          "block w-full resize-none bg-transparent px-1 text-[0.98rem] leading-7 text-foreground outline-none",
          "placeholder:text-muted-foreground",
          compact ? "min-h-16" : "min-h-24",
        )}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
            event.preventDefault()
            submit()
          }
        }}
        placeholder={placeholder}
        ref={textareaRef}
        value={value}
      />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <label className="sq-sm inline-flex min-h-10 items-center gap-2 bg-secondary px-3 text-xs font-semibold text-muted-foreground">
            <LiaLanguageSolid className="size-4" aria-hidden />
            <span className="sr-only">Answer language</span>
            <select
              aria-label="Answer language"
              className="bg-transparent text-xs font-semibold text-foreground outline-none"
              disabled={disabled}
              onChange={(event) =>
                setLanguage(event.target.value as LanguageValue)
              }
              value={language}
            >
              {languageOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <IconButton
            disabled
            label="Attach source document"
            title="Source upload is reserved for a future release"
            type="button"
          >
            <FiPaperclip className="size-4" aria-hidden />
          </IconButton>
          {contextLabel ? (
            <span className="text-xs text-muted-foreground">
              {contextLabel}
            </span>
          ) : null}
        </div>

        <SquircleButton
          aria-label={loading ? "Preparing answer" : "Send question"}
          className="min-w-11 px-0"
          disabled={!value.trim() || disabled}
          loading={loading}
          onClick={submit}
          type="button"
        >
          {loading ? (
            <span className="sr-only">Preparing answer</span>
          ) : (
            <FiSend className="size-4" aria-hidden />
          )}
        </SquircleButton>
      </div>
    </div>
  )
}
