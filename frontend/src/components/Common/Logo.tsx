import { Link } from "@tanstack/react-router"
import { useTranslation } from "react-i18next"

import { cn } from "@/lib/utils"

// Outlined artwork from brand/constitution-ng; regenerate there, don't hand-edit.
const LOCKUP_VIEWBOX = "0 0 1594 197"
const LOCKUP_SYMBOL =
  "M87.31 40.21C76.13 21.64 52.04 10.5 22.28 10.5L14.88 10.5A14.86 14.86 0 0 0 0.02 25.36L0.02 125.64A14.86 14.86 0 0 0 14.88 140.5L22.31 140.5L14.34 170.21L49.76 140.5L34.93 140.5C61.12 140.5 73.34 143.1 87.31 153.5ZM105.88 40.21C117.05 21.64 141.14 10.5 170.91 10.5L178.31 10.5A14.86 14.86 0 0 1 193.16 25.36L193.16 125.64A14.86 14.86 0 0 1 178.31 140.5L158.25 140.5C132.06 140.5 119.84 143.1 105.88 153.5Z"
const LOCKUP_WORDMARK =
  "M342.44 53.45A51.5 51.5 0 1 0 342.44 127.55L328.37 112.98A30.5 32 0 1 1 328.37 68.02ZM456.44 90.5A51.5 51.5 0 0 0 353.44 90.5A51.5 51.5 0 0 0 456.44 90.5ZM435.44 90.5A30.5 32 0 0 1 374.44 90.5A30.5 32 0 0 1 435.44 90.5ZM478.44 140.5L498.44 140.5L498.44 40.5L478.44 40.5ZM566.44 83A44 44 0 0 0 478.44 83L498.44 83A24 25.5 0 0 1 546.44 83ZM546.44 140.5L566.44 140.5L566.44 83L546.44 83ZM652.26 53.58A35.28 29.16 0 1 0 607.36 94.8L627.45 102.19A14.11 11.66 0 1 1 609.49 118.67L591.15 127.42A35.28 29.16 0 1 0 636.06 86.2L615.97 78.81A14.11 11.66 0 1 1 633.93 62.33ZM682.98 102L702.98 102L702.98 12.5L682.98 12.5ZM682.98 102A40 40 0 0 0 722.98 142L722.98 123.5A20 21.5 0 0 1 702.98 102ZM722.98 142L732.98 142L736.98 123.5L722.98 123.5ZM667.98 57.5L728.98 57.5L728.98 40.5L667.98 40.5ZM753.48 140.5L773.48 140.5L773.48 40.5L753.48 40.5ZM775.98 12.5A12.5 12.5 0 0 0 750.98 12.5A12.5 12.5 0 0 0 775.98 12.5ZM806.98 102L826.98 102L826.98 12.5L806.98 12.5ZM806.98 102A40 40 0 0 0 846.98 142L846.98 123.5A20 21.5 0 0 1 826.98 102ZM846.98 142L856.98 142L860.98 123.5L846.98 123.5ZM791.98 57.5L852.98 57.5L852.98 40.5L791.98 40.5ZM961.98 40.5L941.98 40.5L941.98 140.5L961.98 140.5ZM873.98 98A44 44 0 0 0 961.98 98L941.98 98A24 25.5 0 0 1 893.98 98ZM893.98 40.5L873.98 40.5L873.98 98L893.98 98ZM992.98 102L1012.98 102L1012.98 12.5L992.98 12.5ZM992.98 102A40 40 0 0 0 1032.98 142L1032.98 123.5A20 21.5 0 0 1 1012.98 102ZM1032.98 142L1042.98 142L1046.98 123.5L1032.98 123.5ZM977.98 57.5L1038.98 57.5L1038.98 40.5L977.98 40.5ZM1063.48 140.5L1083.48 140.5L1083.48 40.5L1063.48 40.5ZM1085.98 12.5A12.5 12.5 0 0 0 1060.98 12.5A12.5 12.5 0 0 0 1085.98 12.5ZM1210.98 90.5A51.5 51.5 0 0 0 1107.98 90.5A51.5 51.5 0 0 0 1210.98 90.5ZM1189.98 90.5A30.5 32 0 0 1 1128.98 90.5A30.5 32 0 0 1 1189.98 90.5ZM1232.98 140.5L1252.98 140.5L1252.98 40.5L1232.98 40.5ZM1320.98 83A44 44 0 0 0 1232.98 83L1252.98 83A24 25.5 0 0 1 1300.98 83ZM1300.98 140.5L1320.98 140.5L1320.98 83L1300.98 83ZM1362.98 129.5A12.5 12.5 0 0 0 1337.98 129.5A12.5 12.5 0 0 0 1362.98 129.5ZM1381.98 140.5L1401.98 140.5L1401.98 40.5L1381.98 40.5ZM1469.98 83A44 44 0 0 0 1381.98 83L1401.98 83A24 25.5 0 0 1 1449.98 83ZM1449.98 140.5L1469.98 140.5L1469.98 83L1449.98 83ZM1593.98 90.5A51.5 51.5 0 0 0 1490.98 90.5A51.5 51.5 0 0 0 1593.98 90.5ZM1572.98 90.5A30.5 32 0 0 1 1511.98 90.5A30.5 32 0 0 1 1572.98 90.5ZM1573.98 157L1593.98 157L1593.98 40.5L1573.98 40.5ZM1517.73 173.91A40 40 0 0 0 1593.98 157L1573.98 157A20 21.5 0 0 1 1535.63 165.56Z"
// Small-size cut of the symbol (wider gutter, bigger tail) for 16–31 px
const SMALL_SYMBOL =
  "M108 48C95.2 34.25 67.6 26 33.5 26L28 26A20 20 0 0 0 8 46L8 164A20 20 0 0 0 28 184L30 184L18.75 226L68.8 184L48 184C78 184 92 186 108 194ZM148 48C160.8 34.25 188.4 26 222.5 26L228 26A20 20 0 0 1 248 46L248 164A20 20 0 0 1 228 184L208 184C178 184 164 186 148 194Z"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 256 256"
      aria-hidden="true"
      className={cn("size-8 shrink-0 text-brand", className)}
    >
      <path fill="currentColor" d={SMALL_SYMBOL} />
    </svg>
  )
}

function LogoLockup({ className }: { className?: string }) {
  return (
    <svg
      viewBox={LOCKUP_VIEWBOX}
      aria-hidden="true"
      className={cn("h-[1.375rem] w-auto shrink-0", className)}
    >
      <path className="fill-brand" d={LOCKUP_SYMBOL} />
      <path className="fill-foreground" d={LOCKUP_WORDMARK} />
    </svg>
  )
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const { t } = useTranslation()
  const content =
    variant === "icon" ? (
      <LogoMark className={className} />
    ) : (
      <span className="flex min-w-0 items-center">
        <LogoLockup
          className={cn(
            variant === "responsive" && "group-data-[collapsible=icon]:hidden",
            className,
          )}
        />
        {variant === "responsive" && (
          <LogoMark className="hidden size-7 group-data-[collapsible=icon]:block" />
        )}
      </span>
    )

  if (!asLink) {
    return (
      <span role="img" aria-label="constitution.ng">
        {content}
      </span>
    )
  }

  return (
    <Link
      to="/"
      className="sq-md inline-flex min-w-0 items-center focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25"
      aria-label={t("logo.home")}
    >
      {content}
    </Link>
  )
}
