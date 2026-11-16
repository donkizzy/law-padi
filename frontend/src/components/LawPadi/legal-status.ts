import type { IconType } from "react-icons"
import {
  FiAlertTriangle,
  FiArchive,
  FiCheckCircle,
  FiLoader,
} from "react-icons/fi"

export type LegalStatus = "current" | "proposed" | "historical" | "warning"

export const statusMeta: Record<
  LegalStatus,
  {
    icon: IconType
    label: string
    tone: string
    shortLabel: string
  }
> = {
  current: {
    icon: FiCheckCircle,
    label: "Current law",
    shortLabel: "Current",
    tone: "border-[color:var(--legal-emerald)]/20 bg-[color:var(--legal-emerald-soft)] text-[color:var(--legal-emerald-ink)]",
  },
  proposed: {
    icon: FiLoader,
    label: "Proposed change - not currently in force",
    shortLabel: "Proposed",
    tone: "border-[color:var(--legal-amber)]/25 bg-[color:var(--legal-amber-soft)] text-[color:var(--legal-amber)]",
  },
  historical: {
    icon: FiArchive,
    label: "Previous version - superseded",
    shortLabel: "Historical",
    tone: "border-border bg-secondary text-muted-foreground",
  },
  warning: {
    icon: FiAlertTriangle,
    label: "Unable to verify current source",
    shortLabel: "Verify",
    tone: "border-[color:var(--legal-red)]/25 bg-[color:var(--legal-red-soft)] text-[color:var(--legal-red)]",
  },
}
