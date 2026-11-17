import { Link, useNavigate } from "@tanstack/react-router"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { ProvisionView } from "@/components/Constitution/ProvisionView"
import {
  ErrorState,
  InlineAction,
  SkeletonBlock,
} from "@/components/Constitution/primitives"
import { SourcePanel } from "@/components/Constitution/SourcePanel"
import { legalError, useProvision } from "@/hooks/useLegalCorpus"
import { instrumentSlug } from "@/lib/legal-provisions"

export function ProvisionDetail({
  sectionId = "",
  release,
  instrument,
}: {
  sectionId?: string
  release?: string
  instrument?: string
}) {
  const { t } = useTranslation(["legal", "common"])
  const validPath = !instrument || sectionId.startsWith(`${instrument}.`)
  const detail = useProvision(validPath ? sectionId : "", release)
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
          to="/laws/$instrument"
          params={{
            instrument:
              instrument || instrumentSlug({ canonical_path: sectionId }),
          }}
          search={{ release: detail.data?.release_version || release }}
        >
          {t("provision.backToBrowse")}
        </Link>
        {!validPath ? (
          <ErrorState title={t("provision.unavailable")}>
            {t("provision.wrongLaw")}
          </ErrorState>
        ) : detail.isPending ? (
          <SkeletonBlock />
        ) : detail.isError || !detail.data ? (
          <ErrorState
            title={t("provision.unavailable")}
            action={
              <InlineAction onClick={() => detail.refetch()} type="button">
                {t("common:actions.tryAgain")}
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
              void navigate({
                to: "/",
                search: {
                  q,
                  mode: "semantic",
                  intent: "find",
                  instrument: instrumentSlug(detail.data),
                  release: detail.data.release_version,
                },
              })
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
