import { Link } from "@tanstack/react-router"
import { useTranslation } from "react-i18next"
import { editionNote } from "@/lib/legal-provisions"
import { CORRECTIONS_URL, type publicPages } from "@/lib/seo"

export function PublicInformation({
  path,
}: {
  path: keyof typeof publicPages
}) {
  const { t } = useTranslation("pages")
  const page = path === "/about" ? "about" : "methodology"
  const sections = t(`${page}.sections`, {
    returnObjects: true,
    caveat: editionNote("2004 edition"),
  }) as { heading: string; text: string }[]
  return (
    <article className="mx-auto max-w-4xl px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
      <Link to="/welcome" className="text-primary underline">
        constitution.ng
      </Link>
      <h1 className="mt-8 font-display text-title-2">{t(`${page}.heading`)}</h1>
      {sections.map((section) => (
        <section className="mt-8" key={section.heading}>
          <h2 className="font-display text-title-3">{section.heading}</h2>
          <p className="mt-3 text-body-lg leading-7">{section.text}</p>
        </section>
      ))}
      <nav
        aria-label={t("links.label")}
        className="mt-8 flex flex-wrap gap-4 text-sm text-primary underline"
      >
        <Link to="/constitution">{t("links.source")}</Link>
        <Link to="/about">{t("links.about")}</Link>
        <Link to="/methodology">{t("links.methodology")}</Link>
        <a href={CORRECTIONS_URL}>{t("links.corrections")}</a>
        <a href="/methodology/benchmark.json">{t("links.benchmark")}</a>
      </nav>
    </article>
  )
}
