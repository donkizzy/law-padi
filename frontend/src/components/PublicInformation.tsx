import { Link } from "@tanstack/react-router"
import { CORRECTIONS_URL, publicPages } from "@/lib/seo"

export function PublicInformation({
  path,
}: {
  path: keyof typeof publicPages
}) {
  const page = publicPages[path]
  return (
    <article className="mx-auto max-w-4xl px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
      <Link to="/welcome" className="text-primary underline">
        constitution.ng
      </Link>
      <h1 className="mt-8 font-display text-title-2">{page.heading}</h1>
      {page.sections.map((section) => (
        <section className="mt-8" key={section.heading}>
          <h2 className="font-display text-title-3">{section.heading}</h2>
          <p className="mt-3 text-body-lg leading-7">{section.text}</p>
        </section>
      ))}
      <nav
        aria-label="Sources and corrections"
        className="mt-8 flex flex-wrap gap-4 text-sm text-primary underline"
      >
        <Link to="/constitution">Read the source edition</Link>
        <Link to="/about">About and corrections</Link>
        <Link to="/methodology">Retrieval methodology</Link>
        <a href={CORRECTIONS_URL}>
          Corrections on GitHub (repository access required)
        </a>
        <a href="/methodology/benchmark.json">Versioned retrieval test</a>
      </nav>
    </article>
  )
}
