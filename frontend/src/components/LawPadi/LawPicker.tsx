import { useId } from "react"
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
  const id = useId()
  const instruments = useLegalInstruments(release)
  return (
    <div className="mb-5 grid max-w-xl gap-2">
      <label className="text-label text-muted-foreground" htmlFor={id}>
        Law
      </label>
      <select
        id={id}
        aria-label="Law"
        className="sq-md min-h-11 w-full border border-input bg-card px-3 text-body"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={!instruments.data}
      >
        {allowAll && <option value="">All published laws</option>}
        {!instruments.data && !allowAll && (
          <option value={value}>Loading published laws…</option>
        )}
        {instruments.data?.data.map((law) => (
          <option key={law.slug} value={law.slug}>
            {law.short_title || law.title}
          </option>
        ))}
      </select>
      {allowAll && (
        <p className="text-label font-normal text-muted-foreground">
          {value
            ? "Section numbers use this law. A law named in your reference takes priority."
            : "Search across published laws. Bare section numbers refer to the Constitution."}
        </p>
      )}
      {instruments.isError && (
        <p className="text-label text-muted-foreground" role="status">
          The published law list couldn't load.{" "}
          <button
            type="button"
            className="text-primary underline"
            onClick={() => void instruments.refetch()}
          >
            Try again
          </button>
        </p>
      )}
    </div>
  )
}
