import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { AdminService, type ReviewIssuePublic } from "@/client"
import { SquircleButton } from "@/components/LawPadi/primitives"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import useCustomToast from "@/hooks/useCustomToast"

export function ResolveReviewIssueForm({
  issue,
  candidateVersion,
  canOverride,
  disabled,
}: {
  issue: ReviewIssuePublic
  candidateVersion: number
  canOverride: boolean
  disabled: boolean
}) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const [evidenceText, setEvidenceText] = useState("{}")
  const [overrideReason, setOverrideReason] = useState("")
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  let evidence: Record<string, unknown> | undefined
  let error: string | undefined
  try {
    const parsed: unknown = JSON.parse(evidenceText)
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      error = "Evidence must be a JSON object."
    } else {
      evidence = parsed as Record<string, unknown>
    }
  } catch {
    error = "Evidence must be valid JSON."
  }
  const resolve = useMutation({
    mutationFn: () =>
      AdminService.patchReviewIssue({
        path: { issue_id: issue.id },
        body: {
          idempotency_key: `resolve-issue-${crypto.randomUUID()}`,
          expected_version: candidateVersion,
          reason: reason.trim(),
          evidence,
          superuser_override_reason: issue.blocking
            ? overrideReason.trim()
            : null,
        },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin"] })
      showSuccessToast("Review issue resolution recorded.")
      setOpen(false)
    },
    onError: (cause) =>
      showErrorToast(
        cause instanceof Error ? cause.message : "Unable to resolve issue.",
      ),
  })
  if (issue.status !== "open" || (issue.blocking && !canOverride)) return null
  const fieldClass = "sq-sm border border-input bg-background p-3"
  return (
    <>
      <SquircleButton
        className="mt-3"
        type="button"
        size="sm"
        variant="outline"
        disabled={disabled}
        onClick={() => {
          setReason("")
          setEvidenceText("{}")
          setOverrideReason("")
          setOpen(true)
        }}
      >
        Resolve review issue
      </SquircleButton>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Record review issue resolution</DialogTitle>
          </DialogHeader>
          <p className="text-sm">{issue.message}</p>
          {issue.blocking ? (
            <p className="text-sm text-muted-foreground">
              This records a superuser override of a blocking finding. Check the
              source and current candidate inventory, and explain why the
              finding is resolved. Candidate approval remains a separate action.
            </p>
          ) : null}
          <label className="grid gap-1 text-sm">
            Issue resolution reason
            <textarea
              className={fieldClass}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm">
            Resolution evidence JSON
            <textarea
              className={`${fieldClass} min-h-36 font-mono text-xs`}
              value={evidenceText}
              onChange={(event) => setEvidenceText(event.target.value)}
              aria-invalid={Boolean(error)}
            />
          </label>
          {error ? <p role="alert">{error}</p> : null}
          {issue.blocking ? (
            <label className="grid gap-1 text-sm">
              Blocking issue override reason
              <textarea
                className={fieldClass}
                value={overrideReason}
                onChange={(event) => setOverrideReason(event.target.value)}
              />
            </label>
          ) : null}
          <SquircleButton
            type="button"
            loading={resolve.isPending}
            disabled={
              disabled ||
              resolve.isPending ||
              !reason.trim() ||
              Boolean(error) ||
              (issue.blocking &&
                (!overrideReason.trim() || !Object.keys(evidence ?? {}).length))
            }
            onClick={() => resolve.mutate()}
          >
            Record resolution
          </SquircleButton>
        </DialogContent>
      </Dialog>
    </>
  )
}
