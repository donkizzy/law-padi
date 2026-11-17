import { useTranslation } from "react-i18next"
import { FiAlertTriangle } from "react-icons/fi"
import type { ProvisionNotice } from "@/client"
import { cn } from "@/lib/utils"

/** Same notice can arrive from several sources in one answer; show it once. */
export function uniqueNotices(
  lists: (ProvisionNotice[] | null | undefined)[],
): ProvisionNotice[] {
  const seen = new Set<string>()
  const notices: ProvisionNotice[] = []
  for (const notice of lists.flatMap((list) => list ?? [])) {
    const key = `${notice.code}:${notice.text}`
    if (seen.has(key)) continue
    seen.add(key)
    notices.push(notice)
  }
  return notices
}

export function ProvisionNotices({
  notices,
  className,
}: {
  notices?: ProvisionNotice[] | null
  className?: string
}) {
  const { t } = useTranslation("legal")
  if (!notices?.length) return null
  return (
    <div className={cn("grid gap-2", className)}>
      {notices.map((notice) => (
        <p
          key={`${notice.code}:${notice.text}`}
          className="flex gap-2 text-label font-normal text-foreground"
          role="note"
        >
          <FiAlertTriangle
            aria-hidden
            className="mt-0.5 size-4 shrink-0 text-primary"
          />
          <span>
            {t(`provisionNotices.${notice.code}`, {
              ...notice.params,
              defaultValue: notice.text,
            })}
          </span>
        </p>
      ))}
    </div>
  )
}
