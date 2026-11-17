import {
  AdminService,
  type CompletedMultipartPart,
  type CorpusReleasePublic,
  type CorpusReleasePublishRequest,
  type CorpusReleaseValidationRequest,
  type IngestionRunControlRequest,
  type IngestionRunDetail,
  type IngestionRunPublic,
  type PageInclusionStatus,
  type PageSelectionUpdate,
  type SourceDocumentPublic,
  type SourcePagePublic,
  type SourceUploadCreate,
  type SourceUploadPublic,
} from "@/client"
import { client } from "@/client/client.gen"
import { getAccessToken } from "@/lib/session"

export type UploadMutationInput = {
  file: File
  metadata: SourceUploadCreate
}

type PutSourceObjectResult = {
  completedParts?: CompletedMultipartPart[]
  expectedVersion: number
}

const multipartChunkBytes = 100 * 1024 * 1024

export async function uploadSourcePdf(input: UploadMutationInput) {
  const upload = (
    await AdminService.createSourceUpload({ body: input.metadata })
  ).data
  const putResult = await putSourceObject(upload, input.file)
  return (
    await AdminService.completeUpload({
      path: { upload_id: upload.id },
      body: {
        idempotency_key: `complete-${crypto.randomUUID()}`,
        expected_version: putResult.expectedVersion,
        actual_sha256: input.metadata.expected_sha256,
        completed_parts: putResult.completedParts,
      },
    })
  ).data
}

async function putSourceObject(
  upload: SourceUploadPublic,
  file: File,
): Promise<PutSourceObjectResult> {
  if (upload.multipart_required) {
    return putMultipartSourceObject(upload, file)
  }
  const token = getAccessToken()
  const response = await fetch(uploadFetchUrl(upload.upload_url), {
    method: "PUT",
    headers: {
      ...upload.upload_headers,
      ...(upload.upload_backend === "local" && token
        ? { Authorization: `Bearer ${token}` }
        : {}),
    },
    body: file,
  })
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response))
  }
  return {
    expectedVersion:
      upload.upload_backend === "local"
        ? upload.lock_version + 1
        : upload.lock_version,
  }
}

async function putMultipartSourceObject(
  upload: SourceUploadPublic,
  file: File,
): Promise<PutSourceObjectResult> {
  const partCount = Math.max(1, Math.ceil(file.size / multipartChunkBytes))
  const multipart = (
    await AdminService.createMultipartUploadParts({
      path: { upload_id: upload.id },
      body: {
        idempotency_key: `multipart-${crypto.randomUUID()}`,
        expected_version: upload.lock_version,
        part_count: partCount,
      },
    })
  ).data
  const completedParts: CompletedMultipartPart[] = []
  for (const part of multipart.parts) {
    const start = (part.part_number - 1) * multipartChunkBytes
    const end = Math.min(start + multipartChunkBytes, file.size)
    const response = await fetch(uploadFetchUrl(part.upload_url), {
      method: "PUT",
      body: file.slice(start, end),
    })
    if (!response.ok) {
      throw new Error(await responseErrorMessage(response))
    }
    const etag = response.headers.get("etag")
    if (!etag) {
      throw new Error("Multipart upload part did not return an ETag")
    }
    completedParts.push({ part_number: part.part_number, etag })
  }
  return {
    completedParts,
    expectedVersion: upload.lock_version + 1,
  }
}

function uploadFetchUrl(uploadUrl: string): string {
  const apiBaseUrl =
    client.getConfig().baseURL || import.meta.env.VITE_API_URL || ""
  if (!apiBaseUrl || /^https?:\/\//i.test(uploadUrl)) {
    return uploadUrl
  }
  return new URL(uploadUrl, apiBaseUrl).toString()
}

export async function controlRun(
  action: "retry" | "cancel" | "resume",
  run: IngestionRunPublic | IngestionRunDetail,
  reason?: string,
) {
  const body: IngestionRunControlRequest = {
    idempotency_key: `${action}-${crypto.randomUUID()}`,
    expected_version: run.lock_version,
    reason,
  }
  if (action === "retry") {
    return (await AdminService.retryRun({ path: { run_id: run.id }, body }))
      .data
  }
  if (action === "cancel") {
    return (await AdminService.cancelRun({ path: { run_id: run.id }, body }))
      .data
  }
  return (await AdminService.resumeRun({ path: { run_id: run.id }, body })).data
}

export async function verifySourceDocument(
  source: SourceDocumentPublic,
  reason: string,
) {
  return (
    await AdminService.verifyDocumentSource({
      path: { source_document_id: source.id },
      body: {
        idempotency_key: `verify-source-${crypto.randomUUID()}`,
        expected_version: source.lock_version,
        reason,
      },
    })
  ).data
}

export async function mutateRelease(
  release: CorpusReleasePublic,
  action: "validate" | "publish",
  superuserOverrideReason?: string,
) {
  if (action === "validate") {
    const body: CorpusReleaseValidationRequest = {
      idempotency_key: `validate-${crypto.randomUUID()}`,
      expected_version: release.lock_version,
    }
    return (
      await AdminService.validateRelease({
        path: { release_id: release.id },
        body,
      })
    ).data.id
  }
  const body: CorpusReleasePublishRequest = {
    idempotency_key: `publish-${crypto.randomUUID()}`,
    expected_version: release.lock_version,
    superuser_override_reason: superuserOverrideReason ?? null,
  }
  return (
    await AdminService.publishRelease({
      path: { release_id: release.id },
      body,
    })
  ).data.release.id
}

export function pageSelectionBody(
  pages: SourcePagePublic[],
  run?: IngestionRunPublic | IngestionRunDetail,
): PageSelectionUpdate {
  return {
    idempotency_key: `pages-${crypto.randomUUID()}`,
    expected_run_version: run?.lock_version ?? 1,
    pages: pages.map((page) => ({
      page_number: page.page_number,
      inclusion_status: nextInclusionStatus(page.inclusion_status),
      inclusion_reason: page.inclusion_reason ?? "Confirmed by reviewer",
      expected_version: page.lock_version,
    })),
  }
}

function nextInclusionStatus(status: PageInclusionStatus): PageInclusionStatus {
  if (status === "suggested_exclude") return "excluded"
  if (status === "suggested_include") return "included"
  return status
}

export async function sha256File(file: File): Promise<string> {
  const hashBuffer = await crypto.subtle.digest(
    "SHA-256",
    await file.arrayBuffer(),
  )
  return Array.from(new Uint8Array(hashBuffer))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")
}

async function responseErrorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json()
    if (typeof payload.detail === "string") {
      return payload.detail
    }
    if (Array.isArray(payload.detail) && payload.detail[0]?.msg) {
      return payload.detail[0].msg
    }
  } catch {
    return response.statusText
  }
  return response.statusText
}
