import { createFileRoute, Link } from "@tanstack/react-router"
import { amendmentsMetadata } from "@/lib/public-pages"
import { seoHead } from "@/lib/seo"
export const Route = createFileRoute("/_layout/amendments")({
  component: () => (
    <section className="mx-auto max-w-4xl px-4 py-8 sm:px-8">
      <h1 className="font-display text-title-2">
        Amendments are not published here yet
      </h1>
      <p className="mt-4 text-body-lg">
        The available reading edition is historical. Reviewed amendment records
        and comparisons are not available yet.
      </p>
      <Link
        className="mt-4 inline-block text-primary underline"
        to="/constitution"
      >
        Browse the source edition
      </Link>
    </section>
  ),
  head: () => seoHead(amendmentsMetadata),
})
