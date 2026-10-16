import { FiInfo } from "react-icons/fi"
import { editionNote } from "@/lib/legal-provisions"
import { cn } from "@/lib/utils"

export function EditionNotice({
  label,
  historical = true,
  className,
}: {
  label?: string | null
  historical?: boolean
  className?: string
}) {
  if (!historical) return null
  return (
    <p
      className={cn(
        "flex gap-2 text-label font-normal text-muted-foreground",
        className,
      )}
    >
      <FiInfo aria-hidden className="mt-0.5 size-4 shrink-0" />
      <span>{editionNote(label)}</span>
    </p>
  )
}
