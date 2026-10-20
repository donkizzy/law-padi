import { useId } from "react"
import { useTranslation } from "react-i18next"
import { useLegalInstruments } from "@/hooks/useLegalCorpus"

export function LawPicker({
  value,
  onChange,
  release,
  allowAll = false,
}: {
  value: string
  onChange: (slug: string) => void
  release?: string
  allowAll?: boolean
}) {
  const { t } = useTranslation(["legal", "common"])
  const id = useId()
  const instruments = useLegalInstruments(release)
  return (
    <div className="mb-5 grid max-w-xl gap-2">
      <label className="text-label text-muted-foreground" htmlFor={id}>
        {t("picker.label")}
      </label>
      <select
        id={id}
        aria-label={t("picker.label")}
        className="sq-md min-h-11 w-full border border-input bg-card px-3 text-body"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={!instruments.data}
      >
        {allowAll && <option value="">{t("picker.all")}</option>}
        {!instruments.data && !allowAll && (
          <option value={value}>{t("picker.loading")}</option>
        )}
        {instruments.data?.data.map((law) => (
          <option key={law.slug} value={law.slug}>
            {law.short_title || law.title}
          </option>
        ))}
      </select>
      {allowAll && (
        <p className="text-label font-normal text-muted-foreground">
          {value ? t("picker.selectedHint") : t("picker.allHint")}
        </p>
      )}
      {instruments.isError && (
        <p className="text-label text-muted-foreground" role="status">
          {t("picker.loadFailed")}{" "}
          <button
            type="button"
            className="text-primary underline"
            onClick={() => void instruments.refetch()}
          >
            {t("common:actions.tryAgain")}
          </button>
        </p>
      )}
    </div>
  )
}
