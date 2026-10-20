import { FiInfo } from "react-icons/fi"
import { editionNote, type InstrumentContext } from "@/lib/legal-provisions"
import { cn } from "@/lib/utils"

export function EditionNotice({
  label,
  historical = true,
  className,
  notice,
  instrument,
}: {
  label?: string | null
  historical?: boolean
  className?: string
  notice?: string | null
  instrument?: InstrumentContext | string
}) {
  if (!historical && !notice) return null
  return (
    <p
      className={cn(
        "flex gap-2 text-label font-normal text-muted-foreground",
        className,
      )}
    >
      <FiInfo aria-hidden className="mt-0.5 size-4 shrink-0" />
      <span className="whitespace-pre-line">
        {notice || editionNote(label, instrument)}
      </span>
    </p>
  )
}
