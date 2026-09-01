import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

function LogoMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "sq-sm grid size-8 place-items-center bg-primary text-primary-foreground shadow-[var(--shadow-subtle)]",
        "font-legal text-base font-semibold leading-none",
        className,
      )}
    >
      À
    </span>
  )
}

function LogoWordmark({ className }: { className?: string }) {
  return (
    <span className={cn("min-w-0 leading-none", className)}>
      <span className="font-legal block text-[1.08rem] font-semibold text-foreground">
        Àṣẹ
      </span>
      <span className="block text-[0.62rem] font-bold uppercase text-muted-foreground">
        Constitution AI
      </span>
    </span>
  )
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const content =
    variant === "icon" ? (
      <LogoMark className={className} />
    ) : (
      <span className={cn("flex min-w-0 items-center gap-2.5", className)}>
        <LogoMark className="group-data-[collapsible=icon]:size-7" />
        <LogoWordmark
          className={cn(
            variant === "responsive" && "group-data-[collapsible=icon]:hidden",
          )}
        />
      </span>
    )

  if (!asLink) {
    return content
  }

  return (
    <Link
      to="/"
      className="sq-md inline-flex min-w-0 items-center focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25"
      aria-label="Law Padi home"
    >
      {content}
    </Link>
  )
}
