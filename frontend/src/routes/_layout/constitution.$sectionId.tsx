import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"
import { ProvisionDetail } from "@/components/Constitution/ProvisionDetail"
import { provisionQueryOptions } from "@/hooks/useLegalCorpus"
import { publicOrigin } from "@/lib/public-origin"
import { queryClient } from "@/lib/query-client"
import { provisionMetadata, SITE_DESCRIPTION, seoHead } from "@/lib/seo"

export const Route = createFileRoute("/_layout/constitution/$sectionId")({
  validateSearch: z.object({ release: z.string().min(1).max(128).optional() }),
  loaderDeps: ({ search }) => ({ release: search.release }),
  loader: async ({ params, deps }) => {
    try {
      if (!params.sectionId.startsWith("constitution-1999.")) return null
      return await queryClient.fetchQuery(
        provisionQueryOptions(params.sectionId, deps.release),
      )
    } catch {
      return null
    }
  },
  component: ProvisionRoute,
  head: ({ loaderData }) =>
    seoHead(
      loaderData
        ? provisionMetadata(loaderData, publicOrigin)
        : {
            title: "Provision unavailable | constitution.ng",
            description: SITE_DESCRIPTION,
            index: false,
          },
    ),
})

function ProvisionRoute() {
  const { sectionId } = Route.useParams()
  const { release } = Route.useSearch()
  return (
    <ProvisionDetail
      key={`${sectionId}:${release}`}
      instrument="constitution-1999"
      sectionId={sectionId}
      release={release}
    />
  )
}
