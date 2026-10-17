import { Link, useNavigate } from "@tanstack/react-router"
import { useState } from "react"
import { ProvisionView } from "@/components/LawPadi/ProvisionView"
import {
  ErrorState,
  InlineAction,
  SkeletonBlock,
} from "@/components/LawPadi/primitives"
import { SourcePanel } from "@/components/LawPadi/SourcePanel"
import { legalError, useProvision } from "@/hooks/useLegalCorpus"

export function ProvisionDetail({
  sectionId = "",
  release,
}: {
  sectionId?: string
  release?: string
}) {
  const detail = useProvision(sectionId, release)
  const [sourceOpen, setSourceOpen] = useState(false)
  const navigate = useNavigate()
  return (
    <div
      className={
        sourceOpen ? "grid xl:grid-cols-[minmax(0,1fr)_380px]" : "grid"
      }
    >
      <section className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
        <Link
          className="mb-7 inline-block text-sm text-primary hover:underline"
          to="/constitution"
        >
          Back to browse
        </Link>
        {detail.isPending ? (
          <SkeletonBlock />
        ) : detail.isError || !detail.data ? (
          <ErrorState
            title="Provision unavailable"
            action={
              <InlineAction onClick={() => detail.refetch()} type="button">
                Try again
              </InlineAction>
            }
          >
            {legalError(detail.error)}
          </ErrorState>
        ) : (
          <ProvisionView
            primary
            key={detail.data.provision_version_id}
            provision={detail.data}
            onOpenSource={() => setSourceOpen(true)}
            onRelated={(q) => {
              void navigate({ to: "/", search: { q, mode: "semantic" } })
            }}
          />
        )}
      </section>
      {detail.data && (
        <SourcePanel
          open={sourceOpen}
          onOpenChange={setSourceOpen}
          provision={detail.data}
        />
      )}
    </div>
  )
}
