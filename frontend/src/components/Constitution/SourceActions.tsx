import { useTranslation } from "react-i18next"
import { toast } from "sonner"
import { useSavedProvisions } from "@/hooks/useSavedProvisions"
import { type CopySource, evidenceCopy } from "@/lib/research"
import { InlineAction } from "./primitives"

export function SourceActions({ source }: { source: CopySource }) {
  const { t } = useTranslation("legal")
  const { isSaved, toggle } = useSavedProvisions()
  const saved = isSaved(source.canonical_path, source.release_version)
  return (
    <fieldset
      className="flex flex-wrap gap-2"
      aria-label={t("sourceActions.label")}
    >
      <InlineAction
        className="min-h-11"
        type="button"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(evidenceCopy(source))
            toast.success(t("sourceActions.copied"))
          } catch {
            toast.error(t("provision.copyFailed"))
          }
        }}
      >
        {t("sourceActions.copy")}
      </InlineAction>
      <InlineAction
        className="min-h-11"
        type="button"
        aria-pressed={saved}
        onClick={() => {
          try {
            toast.success(
              toggle(source.canonical_path, source.release_version)
                ? t("sourceActions.saved")
                : t("sourceActions.removed"),
            )
          } catch {
            toast.error(t("sourceActions.saveFailed"))
          }
        }}
      >
        {saved ? t("sourceActions.unsave") : t("sourceActions.save")}
      </InlineAction>
    </fieldset>
  )
}
