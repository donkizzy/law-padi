import type { ReactNode } from "react"
import { ErrorBoundary } from "react-error-boundary"
import { useTranslation } from "react-i18next"
import { InlineAction } from "@/components/Constitution/primitives"

function AnswerFailed({ retry }: { retry: () => void }) {
  const { t } = useTranslation(["chat", "common"])
  return (
    <div className="grid justify-items-start gap-2" role="alert">
      <p className="text-body text-muted-foreground">
        {t("answer.loadFailed")}
      </p>
      <InlineAction onClick={retry} type="button">
        {t("common:actions.tryAgain")}
      </InlineAction>
    </div>
  )
}

/**
 * Keeps a render failure in one answer or source panel from replacing the
 * whole app: the rest of the conversation stays usable.
 */
export function AnswerBoundary({
  children,
  resetKey,
}: {
  children: ReactNode
  /** A new value (for example a changed message) clears a previous failure. */
  resetKey?: unknown
}) {
  return (
    <ErrorBoundary
      fallbackRender={({ resetErrorBoundary }) => (
        <AnswerFailed retry={resetErrorBoundary} />
      )}
      resetKeys={[resetKey]}
    >
      {children}
    </ErrorBoundary>
  )
}
