import { createFileRoute } from "@tanstack/react-router"

import { PrivacyNotice } from "@/components/Constitution/PrivacyNotice"

export const Route = createFileRoute("/_layout/privacy")({
  component: PrivacyNotice,
  head: () => ({
    meta: [
      { title: "Privacy - constitution.ng" },
      {
        name: "description",
        content:
          "What constitution.ng keeps, why, for how long, and your rights under the Nigeria Data Protection Act.",
      },
    ],
  }),
})
