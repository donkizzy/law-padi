import { useId, useState } from "react"

import type {
  ProvisionKind,
  ReviewItemPublic,
  ReviewItemUpdate,
} from "@/client"
import { Input } from "@/components/ui/input"

type StructurePatch = Omit<
  ReviewItemUpdate,
  "idempotency_key" | "expected_version" | "reason" | "revised_text"
>

const kinds: ProvisionKind[] = [
  "chapter",
  "part",
  "section",
  "subsection",
  "paragraph",
  "schedule",
  "schedule_item",
]

export function CandidateStructureEditor({
  candidate,
  disabled,
  onChange,
}: {
  candidate: ReviewItemPublic
  disabled: boolean
  onChange: (patch: StructurePatch, error?: string) => void
}) {
  const id = useId()
  const [patch, setPatch] = useState<StructurePatch>({})
  const [spans, setSpans] = useState(
    JSON.stringify(candidate.source_spans ?? [], null, 2),
  )
  const [spanError, setSpanError] = useState<string>()

  const change = (values: StructurePatch) => {
    const next = { ...patch, ...values }
    setPatch(next)
    onChange(next, spanError)
  }

  return (
    <fieldset
      disabled={disabled}
      className="sq-md grid min-w-0 gap-3 border border-border p-4"
    >
      <legend className="px-1 text-sm font-bold">
        Provision structure and source mapping
      </legend>
      <p className="text-sm text-muted-foreground">
        Check each change against the scan. Structure changes share the revision
        reason and audit history.
      </p>
      <div className="grid min-w-0 gap-3 md:grid-cols-2">
        <label className="grid gap-1 text-sm" htmlFor={`${id}-kind`}>
          Provision kind
          <select
            id={`${id}-kind`}
            className="sq-sm min-h-10 border border-input bg-background px-3"
            value={patch.kind ?? candidate.kind}
            onChange={(event) =>
              change({ kind: event.target.value as ProvisionKind })
            }
          >
            {kinds.map((kind) => (
              <option key={kind} value={kind}>
                {kind.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm" htmlFor={`${id}-number`}>
          Provision number
          <Input
            id={`${id}-number`}
            value={
              patch.number !== undefined
                ? (patch.number ?? "")
                : (candidate.number ?? "")
            }
            onChange={(event) => change({ number: event.target.value || null })}
          />
        </label>
        <label
          className="grid gap-1 text-sm md:col-span-2"
          htmlFor={`${id}-heading`}
        >
          Provision heading
          <Input
            id={`${id}-heading`}
            value={
              patch.heading !== undefined
                ? (patch.heading ?? "")
                : (candidate.heading ?? "")
            }
            onChange={(event) =>
              change({ heading: event.target.value || null })
            }
          />
        </label>
        <label
          className="grid gap-1 text-sm md:col-span-2"
          htmlFor={`${id}-path`}
        >
          Canonical path
          <Input
            id={`${id}-path`}
            value={patch.canonical_path ?? candidate.canonical_path}
            onChange={(event) => change({ canonical_path: event.target.value })}
          />
        </label>
        <label className="grid gap-1 text-sm" htmlFor={`${id}-sort`}>
          Sort key
          <Input
            id={`${id}-sort`}
            value={patch.sort_key ?? candidate.sort_key}
            onChange={(event) => change({ sort_key: event.target.value })}
          />
        </label>
        <label className="grid gap-1 text-sm" htmlFor={`${id}-parent`}>
          Parent candidate ID
          <Input
            id={`${id}-parent`}
            value={
              patch.parent_candidate_id !== undefined
                ? (patch.parent_candidate_id ?? "")
                : (candidate.parent_candidate_id ?? "")
            }
            placeholder="Leave empty for a root provision"
            onChange={(event) =>
              change({ parent_candidate_id: event.target.value || null })
            }
          />
        </label>
        <label className="grid gap-1 text-sm" htmlFor={`${id}-start`}>
          Source start page
          <Input
            id={`${id}-start`}
            type="number"
            min={1}
            value={patch.source_page_start ?? candidate.source_page_start ?? ""}
            onChange={(event) =>
              change({
                source_page_start: event.target.value
                  ? Number(event.target.value)
                  : null,
              })
            }
          />
        </label>
        <label className="grid gap-1 text-sm" htmlFor={`${id}-end`}>
          Source end page
          <Input
            id={`${id}-end`}
            type="number"
            min={1}
            value={patch.source_page_end ?? candidate.source_page_end ?? ""}
            onChange={(event) =>
              change({
                source_page_end: event.target.value
                  ? Number(event.target.value)
                  : null,
              })
            }
          />
        </label>
      </div>
      <label className="grid min-w-0 gap-1 text-sm">
        Source spans JSON
        <textarea
          className="sq-sm min-h-32 w-full min-w-0 resize-y border border-input bg-background p-3 font-mono text-xs"
          value={spans}
          aria-invalid={Boolean(spanError)}
          onChange={(event) => {
            setSpans(event.target.value)
            try {
              const parsed: unknown = JSON.parse(event.target.value)
              if (
                !Array.isArray(parsed) ||
                parsed.some(
                  (span) =>
                    !span || typeof span !== "object" || Array.isArray(span),
                )
              ) {
                throw new Error("Use an array of source span objects.")
              }
              const next = { ...patch, source_spans: parsed }
              setPatch(next)
              setSpanError(undefined)
              onChange(next)
            } catch {
              const message = "Source spans must be a JSON array of objects."
              setSpanError(message)
              onChange(patch, message)
            }
          }}
        />
      </label>
      {spanError ? (
        <p role="alert" className="text-sm text-destructive">
          {spanError}
        </p>
      ) : null}
    </fieldset>
  )
}
