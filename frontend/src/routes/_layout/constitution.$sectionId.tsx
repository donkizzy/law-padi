import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"

import { ProvisionDetail } from "@/components/LawPadi/ProvisionDetail"

export const Route = createFileRoute("/_layout/constitution/$sectionId")({
  validateSearch: z.object({ release: z.string().min(1).max(128).optional() }),
  component: ProvisionRoute,
  head: () => ({
    meta: [
      {
        title: "Provision Detail - Law Padi",
      },
    ],
  }),
})

function ProvisionRoute() {
  const { sectionId } = Route.useParams()
  const { release } = Route.useSearch()

  return (
    <ProvisionDetail
      key={`${sectionId}:${release}`}
      sectionId={sectionId}
      release={release}
    />
  )
}
