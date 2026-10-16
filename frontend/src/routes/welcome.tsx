import { createFileRoute } from "@tanstack/react-router"

import { faqs, LandingPage } from "@/components/Landing/LandingPage"

const description =
  "Ask about your rights under Nigeria's Constitution and get the exact section, explained in plain English with the official wording beside it. Free, no account needed."

export const Route = createFileRoute("/welcome")({
  component: LandingPage,
  head: () => ({
    meta: [
      { title: "constitution.ng · Nigeria's Constitution in plain English" },
      { name: "description", content: description },
      { property: "og:type", content: "website" },
      { property: "og:site_name", content: "constitution.ng" },
      {
        property: "og:title",
        content: "Ask about your rights. Get the exact section.",
      },
      { property: "og:description", content: description },
      { name: "twitter:card", content: "summary" },
    ],
    scripts: [
      {
        type: "application/ld+json",
        children: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "FAQPage",
          mainEntity: faqs.map((item) => ({
            "@type": "Question",
            name: item.q,
            acceptedAnswer: { "@type": "Answer", text: item.a },
          })),
        }),
      },
    ],
  }),
})
