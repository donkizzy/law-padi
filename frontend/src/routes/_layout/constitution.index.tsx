import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"
import { BrowseConstitution } from "@/components/LawPadi/BrowseConstitution"
import { treeQueryOptions } from "@/hooks/useLegalCorpus"
import { publicOrigin } from "@/lib/public-origin"
import { queryClient } from "@/lib/query-client"
import { browsePath, pageSchema, SITE_DESCRIPTION, seoHead } from "@/lib/seo"

export const Route = createFileRoute("/_layout/constitution/")({
  validateSearch: z.object({
    parent: z.string().min(1).max(512).optional(),
    release: z.string().min(1).max(128).optional(),
  }),
  loaderDeps: ({ search }) => search,
  loader: async ({ deps }) => {
    try {
      return await queryClient.fetchQuery(
        treeQueryOptions(deps.parent, deps.release),
      )
    } catch {
      return null
    }
  },
  component: () => {
    const search = Route.useSearch()
    return (
      <BrowseConstitution parent={search.parent} release={search.release} />
    )
  },
  head: ({ loaderData, match }) => {
    if (!loaderData)
      return seoHead({
        title: "Browse Constitution | constitution.ng",
        description: SITE_DESCRIPTION,
        index: false,
      })
    const parent = match.loaderDeps.parent
    const title = `${loaderData.parent?.citation ?? "Browse Nigeria's Constitution"}${loaderData.parent?.title ? `: ${loaderData.parent.title}` : ""} | source edition | constitution.ng`
    const canonical = `${publicOrigin}${browsePath(parent, loaderData.release_version)}`
    return seoHead({
      title,
      description: `Read the published chapters and sections in ${loaderData.edition_label}. Later amendments are not included.`,
      canonical,
      index: true,
      schema: [pageSchema(title, canonical, SITE_DESCRIPTION)],
    })
  },
})
