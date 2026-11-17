import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"
import { BrowseConstitution } from "@/components/Constitution/BrowseConstitution"
import { treeQueryOptions } from "@/hooks/useLegalCorpus"
import { lawName } from "@/lib/legal-provisions"
import { publicOrigin } from "@/lib/public-origin"
import { queryClient } from "@/lib/query-client"
import { browsePath, pageSchema, SITE_DESCRIPTION, seoHead } from "@/lib/seo"
export const Route = createFileRoute("/_layout/laws/$instrument/")({
  validateSearch: z.object({
    parent: z.string().min(1).max(512).optional(),
    release: z.string().min(1).max(128).optional(),
  }),
  loaderDeps: ({ search }) => search,
  loader: async ({ deps, params }) => {
    try {
      return await queryClient.fetchQuery(
        treeQueryOptions(deps.parent, deps.release, params.instrument),
      )
    } catch {
      return null
    }
  },
  component: () => {
    const { instrument } = Route.useParams()
    const search = Route.useSearch()
    return (
      <BrowseConstitution
        instrument={instrument}
        parent={search.parent}
        release={search.release}
      />
    )
  },
  head: ({ loaderData, match }) => {
    const instrument = match.params.instrument
    const title = `${loaderData?.parent?.citation || `Browse ${lawName(instrument)}`} | constitution.ng`
    if (!loaderData)
      return seoHead({ title, description: SITE_DESCRIPTION, index: false })
    const canonical =
      publicOrigin +
      browsePath(
        match.loaderDeps.parent,
        loaderData.release_version,
        instrument,
      )
    const description = `Read the published parts and sections of ${lawName(instrument)}. Check its source edition; later amendments may differ.`
    return seoHead({
      title,
      description,
      canonical,
      index: true,
      schema: [pageSchema(title, canonical, description)],
    })
  },
})
