import { Slot, Slottable } from "@radix-ui/react-slot"
import type { ComponentProps, ReactNode } from "react"
import {
  FiAlertCircle,
  FiArrowRight,
  FiCheck,
  FiChevronRight,
  FiCopy,
  FiLoader,
  FiX,
} from "react-icons/fi"
import { LiaBalanceScaleSolid } from "react-icons/lia"

import {
  type LegalStatus,
  statusMeta,
  type TimelineEvent,
} from "@/lib/law-padi-data"
import { cn } from "@/lib/utils"

type ButtonVariant = "primary" | "secondary" | "ghost" | "outline" | "danger"
type ButtonSize = "sm" | "md" | "lg"

const buttonVariant: Record<ButtonVariant, string> = {
  primary:
    "border border-primary bg-primary text-primary-foreground shadow-[var(--shadow-subtle)] hover:bg-[color:var(--legal-emerald-ink)]",
  secondary:
    "border border-transparent bg-secondary text-secondary-foreground hover:bg-muted",
  ghost:
    "border border-transparent bg-transparent text-muted-foreground hover:bg-secondary hover:text-foreground",
  outline:
    "border border-border bg-card text-foreground hover:border-primary/35 hover:bg-accent hover:text-accent-foreground",
  danger:
    "border border-[color:var(--legal-red)]/25 bg-[color:var(--legal-red-soft)] text-[color:var(--legal-red)] hover:border-[color:var(--legal-red)]/45",
}

const buttonSize: Record<ButtonSize, string> = {
  sm: "min-h-9 px-3 py-2 text-xs",
  md: "min-h-11 px-4 py-2.5 text-sm",
  lg: "min-h-12 px-5 py-3 text-sm",
}

export function SquircleButton({
  children,
  className,
  variant = "primary",
  size = "md",
  loading = false,
  ...props
}: ComponentProps<"button"> & {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  asChild?: boolean
}) {
  const { asChild = false, disabled, ...buttonProps } = props
  const Comp = asChild ? Slot : "button"

  return (
    <Comp
      className={cn(
        "sq-sm inline-flex items-center justify-center gap-2 font-semibold transition duration-200",
        "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25",
        "disabled:pointer-events-none disabled:opacity-50",
        buttonVariant[variant],
        buttonSize[size],
        className,
      )}
      disabled={asChild ? undefined : loading || disabled}
      {...buttonProps}
    >
      {loading ? (
        <FiLoader className="size-4 animate-spin" aria-hidden />
      ) : null}
      <Slottable>{children}</Slottable>
    </Comp>
  )
}

export function IconButton({
  label,
  className,
  children,
  ...props
}: ComponentProps<"button"> & {
  label: string
  children: ReactNode
}) {
  return (
    <button
      aria-label={label}
      className={cn(
        "sq-sm grid size-11 place-items-center border border-transparent text-muted-foreground transition duration-200",
        "hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25",
        "disabled:pointer-events-none disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}

export function StatusBadge({
  status,
  label,
  className,
}: {
  status: LegalStatus
  label?: string
  className?: string
}) {
  const meta = statusMeta[status]
  const Icon = meta.icon

  return (
    <span
      className={cn(
        "sq-sm inline-flex w-fit items-center gap-1.5 border px-2.5 py-1.5 text-[0.72rem] font-bold leading-none",
        meta.tone,
        className,
      )}
    >
      <Icon className="size-3.5" aria-hidden />
      {label ?? meta.label}
    </span>
  )
}

export function CitationChip({
  children,
  className,
  ...props
}: ComponentProps<"button">) {
  return (
    <button
      className={cn(
        "sq-xs inline-flex min-h-7 items-center gap-1 border border-[color:var(--legal-blue)]/15",
        "bg-[color:var(--legal-blue-soft)] px-2 py-0.5 align-baseline text-xs font-bold text-[color:var(--legal-blue)]",
        "transition hover:border-[color:var(--legal-blue)]/35 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25",
        className,
      )}
      type="button"
      {...props}
    >
      {children}
    </button>
  )
}

export function PromptSuggestion({
  children,
  className,
  ...props
}: ComponentProps<"button">) {
  return (
    <button
      className={cn(
        "sq-sm border border-border bg-card/60 px-3 py-2 text-left text-xs font-medium text-muted-foreground",
        "transition hover:border-primary/30 hover:bg-accent hover:text-accent-foreground",
        "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25",
        className,
      )}
      type="button"
      {...props}
    >
      {children}
    </button>
  )
}

export function SectionHeading({
  kicker,
  title,
  children,
  action,
}: {
  kicker?: string
  title: string
  children?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        {kicker ? (
          <div className="mb-3 text-[0.7rem] font-bold uppercase text-primary">
            {kicker}
          </div>
        ) : null}
        <h1 className="font-legal text-[2rem] leading-[1.05] text-foreground sm:text-[2.6rem]">
          {title}
        </h1>
        {children ? (
          <div className="mt-3 text-sm leading-7 text-muted-foreground">
            {children}
          </div>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  )
}

export function OfficialTextBlock({
  title = "Official wording",
  children,
  className,
}: {
  title?: string
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={cn(
        "sq-lg border border-border bg-card p-5 shadow-[var(--shadow-subtle)]",
        className,
      )}
    >
      <h2 className="mb-3 text-[0.72rem] font-bold uppercase text-muted-foreground">
        {title}
      </h2>
      <div className="font-legal border-l-2 border-primary/35 pl-4 text-[1.02rem] leading-8 text-foreground/90">
        {children}
      </div>
    </section>
  )
}

export function TranslationBlock() {
  return (
    <details className="sq-md border border-border bg-card/70 p-4">
      <summary className="flex cursor-pointer items-center justify-between gap-3 text-sm font-semibold text-foreground">
        <span>Show Yorùbá translation</span>
        <FiChevronRight className="size-4 text-muted-foreground" aria-hidden />
      </summary>
      <div className="mt-4 border-t border-border pt-4 text-sm leading-7 text-muted-foreground">
        <p className="mb-2 font-semibold text-foreground">
          Translation for accessibility
        </p>
        <p>
          Àṣírí àwọn ará ilu, ilé wọn, ìbánisọrọ àti ìfọ̀rọ̀wérọ̀ lórí foonu ni a
          dáàbò bo.
        </p>
        <p className="mt-3 text-xs">
          Official legal wording is the English text above.
        </p>
      </div>
    </details>
  )
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
  className,
}: {
  options: { label: string; value: T }[]
  value: T
  onChange: (value: T) => void
  ariaLabel: string
  className?: string
}) {
  return (
    <div
      aria-label={ariaLabel}
      className={cn(
        "sq-sm inline-flex w-fit max-w-full gap-1 overflow-auto bg-secondary p-1",
        className,
      )}
      role="tablist"
    >
      {options.map((option) => {
        const selected = value === option.value

        return (
          <button
            aria-selected={selected}
            className={cn(
              "sq-xs min-h-9 whitespace-nowrap px-3 text-xs font-semibold text-muted-foreground transition",
              "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25",
              selected &&
                "bg-card text-foreground shadow-[var(--shadow-subtle)]",
            )}
            key={option.value}
            onClick={() => onChange(option.value)}
            role="tab"
            type="button"
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

export function AmendmentTimeline({
  events,
  className,
}: {
  events: TimelineEvent[]
  className?: string
}) {
  return (
    <div className={cn("grid gap-3", className)}>
      {events.map((event, index) => (
        <div
          className="grid grid-cols-[4.5rem_1fr] gap-3"
          key={`${event.marker}-${event.title}`}
        >
          <div className="pt-0.5 text-xs font-bold text-muted-foreground">
            {event.marker}
          </div>
          <div className="relative pb-4">
            {index < events.length - 1 ? (
              <span
                aria-hidden
                className="absolute left-[0.35rem] top-3 h-full w-px bg-border"
              />
            ) : null}
            <span
              aria-hidden
              className={cn(
                "sq-xs absolute left-0 top-1 size-3 border-2 border-primary/35 bg-card",
                event.status === "proposed" &&
                  "border-[color:var(--legal-amber)]/45",
              )}
            />
            <div className="pl-6">
              <p className="text-sm font-semibold text-foreground">
                {event.title}
              </p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                {event.description}
              </p>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export function VersionDiff({
  previous,
  current,
  className,
}: {
  previous: string
  current: string
  className?: string
}) {
  return (
    <div
      className={cn("sq-lg overflow-hidden border border-border", className)}
    >
      <div className="grid gap-px bg-border md:grid-cols-2">
        <section className="bg-card p-5">
          <h3 className="mb-3 text-[0.72rem] font-bold uppercase text-muted-foreground">
            Previous wording
          </h3>
          <p className="sq-sm bg-[color:var(--legal-red-soft)] p-3 font-legal text-sm leading-7 text-[color:var(--legal-red)] line-through">
            {previous}
          </p>
        </section>
        <section className="bg-card p-5">
          <h3 className="mb-3 text-[0.72rem] font-bold uppercase text-muted-foreground">
            Current wording
          </h3>
          <p className="sq-sm bg-[color:var(--legal-emerald-soft)] p-3 font-legal text-sm leading-7 text-[color:var(--legal-emerald-ink)]">
            {current}
          </p>
        </section>
      </div>
    </div>
  )
}

export function EmptyState({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center py-10 text-center">
      <div className="sq-lg mb-5 grid size-14 place-items-center bg-accent text-accent-foreground">
        <LiaBalanceScaleSolid className="size-6" aria-hidden />
      </div>
      <h2 className="font-legal text-3xl leading-tight text-foreground">
        {title}
      </h2>
      <p className="mt-3 max-w-lg text-sm leading-7 text-muted-foreground">
        {children}
      </p>
    </div>
  )
}

export function ErrorState({
  title,
  children,
  action,
}: {
  title: string
  children: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="sq-lg border border-[color:var(--legal-red)]/20 bg-[color:var(--legal-red-soft)] p-5">
      <div className="flex gap-3">
        <FiAlertCircle
          className="mt-0.5 size-5 shrink-0 text-[color:var(--legal-red)]"
          aria-hidden
        />
        <div>
          <h3 className="font-semibold text-foreground">{title}</h3>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            {children}
          </p>
          {action ? <div className="mt-4">{action}</div> : null}
        </div>
      </div>
    </div>
  )
}

export function SkeletonBlock() {
  return (
    <div aria-live="polite" className="sq-lg border border-border bg-card p-5">
      <div className="mb-4 flex items-center gap-2 text-xs font-semibold text-muted-foreground">
        <FiLoader className="size-4 animate-spin" aria-hidden />
        Checking trusted sources
      </div>
      <div className="grid gap-3">
        <span className="sq-xs h-3 w-4/5 animate-pulse bg-secondary" />
        <span className="sq-xs h-3 w-full animate-pulse bg-secondary" />
        <span className="sq-xs h-3 w-3/5 animate-pulse bg-secondary" />
      </div>
    </div>
  )
}

export function CopyButton({
  copied,
  ...props
}: ComponentProps<"button"> & { copied?: boolean }) {
  return (
    <IconButton label={copied ? "Copied" : "Copy"} {...props}>
      {copied ? (
        <FiCheck className="size-4" aria-hidden />
      ) : (
        <FiCopy className="size-4" aria-hidden />
      )}
    </IconButton>
  )
}

export function InlineAction({
  children,
  className,
  ...props
}: ComponentProps<"button">) {
  return (
    <button
      className={cn(
        "sq-sm inline-flex min-h-10 items-center gap-2 border border-border bg-card px-3 py-2 text-xs font-semibold text-[color:var(--legal-blue)]",
        "transition hover:border-[color:var(--legal-blue)]/35 hover:bg-[color:var(--legal-blue-soft)] focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25",
        className,
      )}
      type="button"
      {...props}
    >
      {children}
      <FiArrowRight className="size-3.5" aria-hidden />
    </button>
  )
}

export function CloseButton(props: ComponentProps<"button">) {
  return (
    <IconButton label="Close" {...props}>
      <FiX className="size-4" aria-hidden />
    </IconButton>
  )
}
