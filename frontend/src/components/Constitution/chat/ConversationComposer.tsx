import type { RefObject } from "react"
import { useTranslation } from "react-i18next"
import { FiArrowDown } from "react-icons/fi"
import { ChatComposer } from "@/components/Constitution/ChatComposer"
import {
  PromptSuggestion,
  SquircleButton,
} from "@/components/Constitution/primitives"

type ConversationComposerProps = {
  bottomRef: RefObject<HTMLDivElement | null>
  showJump: boolean
  onJumpToLatest: () => void
  explanationsEnabled?: boolean
  inputRef: RefObject<HTMLTextAreaElement | null>
  autoFocus: boolean
  draft: string
  onDraftChange: (value: string) => void
  onSubmit: () => void
  submitting: boolean
  disabled: boolean
  compact: boolean
  contextLabel?: string
  showSuggestions: boolean
}

/** The question editor pinned below the conversation, with its prompts and notices. */
export function ConversationComposer({
  bottomRef,
  showJump,
  onJumpToLatest,
  explanationsEnabled,
  inputRef,
  autoFocus,
  draft,
  onDraftChange,
  onSubmit,
  submitting,
  disabled,
  compact,
  contextLabel,
  showSuggestions,
}: ConversationComposerProps) {
  const { t } = useTranslation(["chat", "common"])
  return (
    <div
      ref={bottomRef}
      className="sticky bottom-0 mt-8 bg-background/95 pb-5 pt-3 backdrop-blur"
    >
      {showJump && (
        <SquircleButton
          className="mb-3"
          type="button"
          size="sm"
          variant="outline"
          onClick={onJumpToLatest}
        >
          <FiArrowDown aria-hidden />
          {t("conversation.jumpToLatest")}
        </SquircleButton>
      )}
      {!explanationsEnabled && (
        <p role="status" className="mb-3 text-body text-muted-foreground">
          {t("home.paused")}
        </p>
      )}
      <ChatComposer
        inputRef={inputRef}
        autoFocus={autoFocus}
        value={draft}
        onChange={onDraftChange}
        onSubmit={onSubmit}
        purpose="explanation"
        loading={submitting}
        disabled={disabled}
        compact={compact}
        contextLabel={contextLabel}
      />
      {showSuggestions && (
        <div className="mt-4 flex flex-wrap gap-2">
          {(t("home.suggestions", { returnObjects: true }) as string[]).map(
            (prompt) => (
              <PromptSuggestion
                key={prompt}
                onClick={() => {
                  onDraftChange(prompt)
                  inputRef.current?.focus()
                }}
                type="button"
              >
                {prompt}
              </PromptSuggestion>
            ),
          )}
        </div>
      )}
      <p className="mt-3 text-label font-normal text-muted-foreground">
        {t("home.disclaimer")}
      </p>
    </div>
  )
}
