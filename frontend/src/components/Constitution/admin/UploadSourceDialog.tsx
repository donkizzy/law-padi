import { type FormEvent, useEffect, useState } from "react"
import { FiUploadCloud } from "react-icons/fi"
import type { SourceUploadCreate } from "@/client"
import {
  sha256File,
  type UploadMutationInput,
} from "@/components/Constitution/admin/api"
import { FieldLabel, inputClass } from "@/components/Constitution/admin/ui"
import { SquircleButton } from "@/components/Constitution/primitives"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import useCustomToast from "@/hooks/useCustomToast"

type UploadFormState = {
  instrument_slug: string
  instrument_title: string
  instrument_short_title: string
  instrument_year: string
  instrument_status: SourceUploadCreate["instrument_status"]
  enacted_at: string
  effective_at: string
  ceased_at: string
  is_legal_revision: boolean
  legal_revision_effective_at: string
  source_title: string
  authority: string
  source_url: string
  source_tier: SourceUploadCreate["source_tier"]
  published_at: string
  retrieved_at: string
}

export function UploadSourceDialog({
  isOpen,
  isUploading,
  onOpenChange,
  onUpload,
}: {
  isOpen: boolean
  isUploading: boolean
  onOpenChange: (open: boolean) => void
  onUpload: (input: UploadMutationInput) => void
}) {
  const { showErrorToast } = useCustomToast()
  const [form, setForm] = useState<UploadFormState>(() => defaultUploadForm())
  const [file, setFile] = useState<File | null>(null)

  useEffect(() => {
    if (!isOpen) {
      setForm(defaultUploadForm())
      setFile(null)
    }
  }, [isOpen])

  const updateField = <T extends keyof UploadFormState>(
    field: T,
    value: UploadFormState[T],
  ) => setForm((current) => ({ ...current, [field]: value }))

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!file) {
      showErrorToast("Choose a PDF source file.")
      return
    }
    if (file.type && file.type !== "application/pdf") {
      showErrorToast("V1 ingestion accepts PDF sources only.")
      return
    }
    if (form.is_legal_revision && !form.legal_revision_effective_at) {
      showErrorToast("Set the legal revision effective date.")
      return
    }
    const expectedSha256 = await sha256File(file)
    onUpload({
      file,
      metadata: {
        idempotency_key: `upload-${crypto.randomUUID()}`,
        expected_size: file.size,
        expected_sha256: expectedSha256,
        original_filename: file.name,
        mime_type: "application/pdf",
        instrument_slug: form.instrument_slug.trim(),
        instrument_title: form.instrument_title.trim(),
        instrument_short_title: form.instrument_short_title.trim() || null,
        instrument_year: Number(form.instrument_year),
        instrument_status: form.instrument_status,
        enacted_at: form.enacted_at || null,
        effective_at: form.effective_at || null,
        ceased_at: form.ceased_at || null,
        is_legal_revision: form.is_legal_revision,
        legal_revision_effective_at: form.is_legal_revision
          ? form.legal_revision_effective_at
          : null,
        source_title: form.source_title.trim(),
        authority: form.authority.trim(),
        source_url: form.source_url.trim(),
        source_tier: form.source_tier,
        published_at: form.published_at,
        retrieved_at: form.retrieved_at,
      },
    })
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Upload Constitution source</DialogTitle>
        </DialogHeader>
        <form className="grid gap-5" onSubmit={handleSubmit}>
          <div className="grid gap-4 md:grid-cols-2">
            <FieldLabel label="Instrument slug">
              <Input
                required
                value={form.instrument_slug}
                onChange={(event) =>
                  updateField("instrument_slug", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Instrument year">
              <Input
                min={1}
                required
                type="number"
                value={form.instrument_year}
                onChange={(event) =>
                  updateField("instrument_year", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel className="md:col-span-2" label="Instrument title">
              <Input
                required
                value={form.instrument_title}
                onChange={(event) =>
                  updateField("instrument_title", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Short title">
              <Input
                value={form.instrument_short_title}
                onChange={(event) =>
                  updateField("instrument_short_title", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Instrument status">
              <select
                className={inputClass}
                required
                value={form.instrument_status}
                onChange={(event) =>
                  updateField(
                    "instrument_status",
                    event.target.value as UploadFormState["instrument_status"],
                  )
                }
              >
                <option value="enacted">Enacted</option>
                <option value="draft">Draft</option>
                <option value="proposed">Proposed</option>
                <option value="superseded">Superseded</option>
              </select>
            </FieldLabel>
            <FieldLabel label="Enacted date">
              <Input
                type="date"
                value={form.enacted_at}
                onChange={(event) =>
                  updateField("enacted_at", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Effective date">
              <Input
                type="date"
                value={form.effective_at}
                onChange={(event) =>
                  updateField("effective_at", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Ceased date">
              <Input
                type="date"
                value={form.ceased_at}
                onChange={(event) =>
                  updateField("ceased_at", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Legal revision">
              <div className="flex min-h-10 items-center gap-3 sq-sm border border-input bg-background px-3">
                <Checkbox
                  aria-label="Legal revision"
                  checked={form.is_legal_revision}
                  onCheckedChange={(checked) =>
                    updateField("is_legal_revision", checked === true)
                  }
                />
                <span className="text-sm font-medium">Changes current law</span>
              </div>
            </FieldLabel>
            <FieldLabel label="Revision effective date">
              <Input
                aria-required={form.is_legal_revision}
                disabled={!form.is_legal_revision}
                type="date"
                value={form.legal_revision_effective_at}
                onChange={(event) =>
                  updateField("legal_revision_effective_at", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Source title">
              <Input
                required
                value={form.source_title}
                onChange={(event) =>
                  updateField("source_title", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Authority">
              <Input
                required
                value={form.authority}
                onChange={(event) =>
                  updateField("authority", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel className="md:col-span-2" label="Source URL">
              <Input
                required
                type="url"
                value={form.source_url}
                onChange={(event) =>
                  updateField("source_url", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Source tier">
              <select
                className={inputClass}
                required
                value={form.source_tier}
                onChange={(event) =>
                  updateField(
                    "source_tier",
                    event.target.value as UploadFormState["source_tier"],
                  )
                }
              >
                <option value="official">Official</option>
                <option value="trusted_secondary">Trusted secondary</option>
                <option value="community">Community</option>
                <option value="unknown">Unknown</option>
              </select>
            </FieldLabel>
            <FieldLabel label="Published date">
              <Input
                required
                type="date"
                value={form.published_at}
                onChange={(event) =>
                  updateField("published_at", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Retrieved date">
              <Input
                required
                type="date"
                value={form.retrieved_at}
                onChange={(event) =>
                  updateField("retrieved_at", event.target.value)
                }
              />
            </FieldLabel>
            <FieldLabel label="Source file">
              <Input
                accept="application/pdf,.pdf"
                required
                type="file"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </FieldLabel>
          </div>
          <DialogFooter>
            <SquircleButton
              disabled={isUploading}
              onClick={() => onOpenChange(false)}
              type="button"
              variant="ghost"
            >
              Cancel
            </SquircleButton>
            <SquircleButton loading={isUploading} type="submit">
              <FiUploadCloud className="size-4" aria-hidden />
              Start ingestion
            </SquircleButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function defaultUploadForm(): UploadFormState {
  const today = new Date().toISOString().slice(0, 10)
  return {
    instrument_slug: "constitution-1999",
    instrument_title: "Constitution of the Federal Republic of Nigeria 1999",
    instrument_short_title: "CFRN 1999",
    instrument_year: "1999",
    instrument_status: "enacted",
    enacted_at: "1999-05-29",
    effective_at: "1999-05-29",
    ceased_at: "",
    is_legal_revision: false,
    legal_revision_effective_at: "",
    source_title: "CFRN 1999 official PDF",
    authority: "Official Gazette",
    source_url: "https://example.test/cfrn-1999.pdf",
    source_tier: "official",
    published_at: "1999-05-29",
    retrieved_at: today,
  }
}
