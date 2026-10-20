import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import {
  AdminService,
  type ReviewItemPublic,
  type ReviewItemUpdate,
} from "@/client"
import { CandidateStructureEditor } from "@/components/LawPadi/CandidateStructureEditor"
import { SquircleButton } from "@/components/LawPadi/primitives"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import useCustomToast from "@/hooks/useCustomToast"

export function DeriveProvisionForm({
  candidate,
  disabled,
  onCreated,
}: {
  candidate: ReviewItemPublic
  disabled: boolean
  onCreated: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [patch, setPatch] = useState<Partial<ReviewItemUpdate>>({})
  const [text, setText] = useState("")
  const [reason, setReason] = useState("")
  const [error, setError] = useState<string>()
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const seed: ReviewItemPublic = {
    ...candidate,
    heading: null,
    number: null,
    kind: "schedule",
    parent_candidate_id: null,
    canonical_path: "",
    sort_key: "",
  }
  const structure = { ...seed, ...patch }
  const hasStructuralHeading =
    (structure.kind === "part" || structure.kind === "chapter") &&
    Boolean(structure.heading?.trim())
  const create = useMutation({
    mutationFn: () =>
      AdminService.deriveReviewItem({
        path: { candidate_id: candidate.id },
        body: {
          idempotency_key: `derive-${crypto.randomUUID()}`,
          expected_version: candidate.lock_version,
          ...(text.trim() ? { revised_text: text.trim() } : {}),
          reason: reason.trim(),
          kind: structure.kind ?? "schedule",
          number: structure.number,
          heading: structure.heading,
          parent_candidate_id: structure.parent_candidate_id,
          canonical_path: structure.canonical_path ?? "",
          sort_key: structure.sort_key ?? "",
          source_page_start: structure.source_page_start ?? 0,
          source_page_end: structure.source_page_end ?? 0,
          source_spans: structure.source_spans ?? [],
        },
      }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["admin"] })
      showSuccessToast("Recovered provision saved for review.")
      setOpen(false)
      if (result.data) onCreated(result.data.id)
    },
    onError: (cause) =>
      showErrorToast(
        cause instanceof Error ? cause.message : "Unable to recover provision.",
      ),
  })
  return (
    <>
      <SquircleButton
        type="button"
        variant="outline"
        disabled={disabled}
        onClick={() => {
          setPatch({})
          setText("")
          setReason("")
          setError(undefined)
          setOpen(true)
        }}
      >
        Add missing provision
      </SquircleButton>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Recover a missing provision</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Copy only wording checked against the source scan. The original
            candidate and its raw extraction remain in the audit history. The
            recovered provision requires its own review.
          </p>
          <CandidateStructureEditor
            key={`${candidate.id}-${open}`}
            candidate={seed}
            disabled={create.isPending}
            onChange={(next, message) => {
              setPatch(next)
              setError(message)
            }}
          />
          <label className="grid gap-1 text-sm">
            Recovered provision text
            <textarea
              className="sq-sm min-h-40 border border-input bg-background p-3"
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm">
            Recovery reason
            <textarea
              className="sq-sm min-h-20 border border-input bg-background p-3"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <SquircleButton
            type="button"
            loading={create.isPending}
            disabled={
              create.isPending ||
              Boolean(error) ||
              (!text.trim() && !hasStructuralHeading) ||
              !reason.trim() ||
              !structure.canonical_path?.trim() ||
              !structure.sort_key?.trim()
            }
            onClick={() => create.mutate()}
          >
            Save recovered provision
          </SquircleButton>
        </DialogContent>
      </Dialog>
    </>
  )
}
