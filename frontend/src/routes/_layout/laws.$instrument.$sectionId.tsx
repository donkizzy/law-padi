import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"
import { ProvisionDetail } from "@/components/Constitution/ProvisionDetail"
import { provisionQueryOptions } from "@/hooks/useLegalCorpus"
import { publicOrigin } from "@/lib/public-origin"
import { queryClient } from "@/lib/query-client"
import { provisionMetadata, SITE_DESCRIPTION, seoHead } from "@/lib/seo"
export const Route = createFileRoute("/_layout/laws/$instrument/$sectionId")({
  validateSearch: z.object({ release: z.string().min(1).max(128).optional() }),
  loaderDeps: ({ search }) => ({ release: search.release }),
  loader: async ({ params, deps }) => {
    if (!params.sectionId.startsWith(`${params.instrument}.`)) return null
    try {
      return await queryClient.fetchQuery(
        provisionQueryOptions(params.sectionId, deps.release),
      )
    } catch {
      return null
    }
  },
  component: () => {
    const { instrument, sectionId } = Route.useParams()
    const { release } = Route.useSearch()
    return (
      <ProvisionDetail
        key={`${instrument}:${sectionId}:${release}`}
        instrument={instrument}
        sectionId={sectionId}
        release={release}
      />
    )
  },
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
