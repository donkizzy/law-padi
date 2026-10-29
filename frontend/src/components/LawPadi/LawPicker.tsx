import { useId } from "react"
import { useTranslation } from "react-i18next"
import { FiChevronDown } from "react-icons/fi"
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
    <div className="my-6 grid max-w-xl gap-3 sm:my-8">
      <label className="text-label text-muted-foreground" htmlFor={id}>
        {t("picker.label")}
      </label>
      <div className="relative">
        <select
          id={id}
          aria-label={t("picker.label")}
          className="sq-md min-h-11 w-full appearance-none border border-input bg-card py-3 pl-4 pr-12 text-body"
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
        <FiChevronDown
          aria-hidden
          className="pointer-events-none absolute right-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
        />
      </div>
      {allowAll && (
        <p className="text-label font-normal leading-5 text-muted-foreground">
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
