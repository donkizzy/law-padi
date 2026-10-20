import { useId, useState } from "react"

import type { CompositeReleaseCreate, CorpusReleasePublic } from "@/client"
import { SquircleButton } from "@/components/LawPadi/primitives"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"

export function ComposeReleaseForm({
  releases,
  canCompose,
  isPending,
  onCompose,
}: {
  releases: CorpusReleasePublic[]
  canCompose: boolean
  isPending: boolean
  onCompose: (body: CompositeReleaseCreate) => void
}) {
  const [version, setVersion] = useState("")
  const versionId = useId()
  const [memberIds, setMemberIds] = useState<string[]>([])
  const base = releases.find(
    (release) =>
      release.status === "production" &&
      release.instrument_types?.includes("constitution"),
  )
  const eligible = releases.filter(
    (release) =>
      release.status === "approved" &&
      release.instrument_slugs?.length === 1 &&
      release.instrument_types?.length === 1 &&
      release.instrument_types[0] === "act",
  )
  const members = eligible.filter((release) => memberIds.includes(release.id))

  return (
    <form
      aria-label="Compose release"
      className="mb-5 grid gap-3 border-b border-border pb-5"
      onSubmit={(event) => {
        event.preventDefault()
        if (!base || !members.length || !canCompose || isPending) return
        onCompose({
          version: version.trim(),
          base_release_id: base.id,
          expected_base_version: base.lock_version,
          members: members.map((member) => ({
            release_id: member.id,
            expected_version: member.lock_version,
          })),
          idempotency_key: `compose-${crypto.randomUUID()}`,
        })
      }}
    >
      <h3 className="text-sm font-bold">Compose release</h3>
      <p className="text-xs text-muted-foreground">
        Combine the production Constitution with approved Act releases. The new
        release follows the existing indexing and publication review.
      </p>
      <p className="text-xs">
        Base: {base?.version ?? "Production Constitution required"}
      </p>
      <label className="grid gap-1 text-xs font-semibold" htmlFor={versionId}>
        Release version
        <Input
          id={versionId}
          disabled={!canCompose || isPending}
          maxLength={128}
          onChange={(event) => setVersion(event.target.value)}
          pattern={"[a-zA-Z0-9][a-zA-Z0-9._\\-]*"}
          placeholder="laws-reviewed-01"
          required
          value={version}
        />
      </label>
      {eligible.length ? (
        <fieldset className="grid gap-2" disabled={!canCompose || isPending}>
          <legend className="mb-2 text-xs font-semibold">
            Approved Act releases
          </legend>
          {eligible.map((member) => (
            <label
              className="flex items-center gap-2 text-xs"
              key={member.id}
              htmlFor={`compose-member-${member.id}`}
            >
              <Checkbox
                id={`compose-member-${member.id}`}
                checked={memberIds.includes(member.id)}
                onCheckedChange={(checked) =>
                  setMemberIds((previous) =>
                    checked
                      ? [...previous, member.id]
                      : previous.filter((id) => id !== member.id),
                  )
                }
              />
              {member.instrument_slugs?.[0]} · {member.version}
            </label>
          ))}
        </fieldset>
      ) : (
        <p className="text-xs text-muted-foreground">
          Approve an Act release before composing.
        </p>
      )}
      <SquircleButton
        disabled={
          !canCompose ||
          isPending ||
          !base ||
          !members.length ||
          !version.trim()
        }
        type="submit"
      >
        {isPending ? "Composing…" : "Compose release"}
      </SquircleButton>
    </form>
  )
}
