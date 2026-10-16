import { toast } from "sonner"
import { useSavedProvisions } from "@/hooks/useSavedProvisions"
import { type CopySource, evidenceCopy } from "@/lib/research"
import { InlineAction } from "./primitives"

export function SourceActions({ source }: { source: CopySource }) {
  const { isSaved, toggle } = useSavedProvisions()
  const saved = isSaved(source.canonical_path, source.release_version)
  return (
    <fieldset className="flex flex-wrap gap-2" aria-label="Source actions">
      <InlineAction
        className="min-h-11"
        type="button"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(evidenceCopy(source))
            toast.success("Source and citation copied")
          } catch {
            toast.error("Couldn't copy. Please try again.")
          }
        }}
      >
        Copy source
      </InlineAction>
      <InlineAction
        className="min-h-11"
        type="button"
        aria-pressed={saved}
        onClick={() => {
          try {
            toast.success(
              toggle(source.canonical_path, source.release_version)
                ? "Source saved"
                : "Source removed from saved",
            )
          } catch {
            toast.error("Couldn't save on this browser.")
          }
        }}
      >
        {saved ? "Remove saved source" : "Save source"}
      </InlineAction>
    </fieldset>
  )
}
