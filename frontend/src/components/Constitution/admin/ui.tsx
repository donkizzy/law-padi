import {
  cloneElement,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react"
import { FiCheckCircle, FiClock, FiXCircle } from "react-icons/fi"
import { labelize } from "@/components/Constitution/admin/format"
import { cn } from "@/lib/utils"

export const inputClass =
  "sq-sm min-h-10 border border-input bg-background px-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-ring/20"

export function Panel({
  title,
  count,
  action,
  children,
}: {
  title: string
  count?: number
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="sq-lg min-w-0 border border-border bg-card p-5 shadow-[var(--shadow-subtle)]">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="font-display text-xl text-foreground">{title}</h2>
          {typeof count === "number" ? (
            <span className="sq-xs bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
              {count}
            </span>
          ) : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

export function SmallStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="sq-md border border-border bg-background p-3">
      <p className="text-xs font-semibold text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-bold text-foreground">{value}</p>
    </div>
  )
}

export function StatusPill({ status }: { status?: string | null }) {
  return (
    <span className="sq-xs inline-flex w-fit items-center gap-1.5 border border-border bg-secondary px-2 py-1 text-xs font-bold text-secondary-foreground">
      {statusIcon(status)}
      {labelize(status ?? "unknown")}
    </span>
  )
}

function statusIcon(status?: string | null) {
  if (!status) {
    return <FiClock className="size-3.5" aria-hidden />
  }
  if (
    ["succeeded", "approved", "production", "published", "ready"].includes(
      status,
    )
  ) {
    return <FiCheckCircle className="size-3.5" aria-hidden />
  }
  if (["failed", "cancelled", "rejected"].includes(status)) {
    return <FiXCircle className="size-3.5" aria-hidden />
  }
  return <FiClock className="size-3.5" aria-hidden />
}

export function TextBlock({
  title,
  children,
}: {
  title: string
  children?: ReactNode
}) {
  return (
    <div className="sq-md border border-border bg-background p-4">
      <p className="mb-3 text-xs font-bold uppercase text-muted-foreground">
        {title}
      </p>
      <pre className="whitespace-pre-wrap font-sans text-sm leading-7 text-foreground">
        {children || "No text recorded."}
      </pre>
    </div>
  )
}

export function FieldLabel({
  label,
  children,
  className,
}: {
  label: string
  children: ReactNode
  className?: string
}) {
  const labelledChild = isValidElement<{ "aria-label"?: string }>(children)
    ? cloneElement(children as ReactElement<{ "aria-label"?: string }>, {
        "aria-label": children.props["aria-label"] ?? label,
      })
    : children

  return (
    <div className={cn("grid gap-2 text-sm font-semibold", className)}>
      <span>{label}</span>
      {labelledChild}
    </div>
  )
}

export function ListState({
  isLoading,
  isEmpty,
  text = "No records yet.",
}: {
  isLoading: boolean
  isEmpty: boolean
  text?: string
}) {
  if (isLoading) {
    return <EmptyState text="Loading..." />
  }
  if (isEmpty) {
    return <EmptyState text={text} />
  }
  return null
}

export function EmptyState({ text }: { text: string }) {
  return (
    <div className="sq-md border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
      {text}
    </div>
  )
}
