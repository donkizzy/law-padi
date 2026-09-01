import { createFileRoute } from "@tanstack/react-router"

import { ProvisionDetail } from "@/components/LawPadi/ProvisionDetail"

export const Route = createFileRoute("/_layout/constitution/$sectionId")({
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

  return <ProvisionDetail sectionId={sectionId} />
}
