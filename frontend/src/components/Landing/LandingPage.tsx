import { Link as RouterLink, useNavigate } from "@tanstack/react-router"
import {
  type ComponentProps,
  type FormEvent,
  type ReactNode,
  useEffect,
  useId,
  useRef,
  useState,
} from "react"
import { Trans, useTranslation } from "react-i18next"
import {
  FiArrowRight,
  FiBookmark,
  FiBookOpen,
  FiCheckCircle,
  FiChevronDown,
  FiInfo,
  FiMessageCircle,
  FiSearch,
} from "react-icons/fi"

import { Appearance } from "@/components/Common/Appearance"
import { LanguageMenu } from "@/components/Common/LanguagePicker"
import { Logo } from "@/components/Common/Logo"
import { SquircleButton } from "@/components/Constitution/primitives"
import { useInView } from "@/hooks/useInView"
import { cn } from "@/lib/utils"

// Heavy, springy motion used by every landing transition.
const fluid = "transition-all duration-700 ease-[cubic-bezier(0.32,0.72,0,1)]"

const navLinks = [
  { id: "how-it-works", label: "nav.howItWorks" },
  { id: "examples", label: "nav.examples" },
  { id: "faq", label: "nav.faq" },
] as const

export function LandingPage() {
  const { t, i18n } = useTranslation("landing")
  return (
    <div className="min-h-svh bg-background text-foreground" id="top">
      <a
        className="sq-sm fixed left-4 top-4 z-[60] -translate-y-24 bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground focus-visible:translate-y-0 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25"
        href="#main"
      >
        {t("skip")}
      </a>
      <IslandNav />
      <main id="main">
        <Hero />
        <ProblemSection />
        {/* Remount so the word observer sees the new language's words. */}
        <TaglineReveal key={i18n.resolvedLanguage} />
        <Benefits />
        <HowItWorks />
        <Proof />
        <Faq />
        <FinalCta />
      </main>
      <SiteFooter />
    </div>
  )
}

/* Navigation */

function useActiveSection(ids: string[]) {
  const [active, setActive] = useState<string | null>(null)
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries)
          if (entry.isIntersecting) setActive(entry.target.id)
      },
      { rootMargin: "-45% 0px -50% 0px" },
    )
    for (const id of ids) {
      const node = document.getElementById(id)
      if (node) observer.observe(node)
    }
    return () => observer.disconnect()
  }, [ids])
  return active
}

const sectionIds = navLinks.map((link) => link.id)

function IslandNav() {
  const { t } = useTranslation("landing")
  const [open, setOpen] = useState(false)
  const active = useActiveSection(sectionIds)

  useEffect(() => {
    const close = () => setOpen(false)
    window.addEventListener("hashchange", close)
    return () => window.removeEventListener("hashchange", close)
  }, [])

  useEffect(() => {
    if (!open) return
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false)
    }
    document.body.style.overflow = "hidden"
    window.addEventListener("keydown", close)
    return () => {
      document.body.style.overflow = ""
      window.removeEventListener("keydown", close)
    }
  }, [open])

  return (
    <>
      <header className="pointer-events-none fixed inset-x-0 top-0 z-50 px-4">
        <nav
          aria-label={t("nav.label")}
          className={cn(
            "sq-lg pointer-events-auto mx-auto mt-6 flex w-full max-w-max items-center gap-2 border border-border bg-card/75 py-2 pl-4 pr-2 shadow-[var(--shadow-subtle)] backdrop-blur-xl",
            fluid,
          )}
        >
          <a
            aria-label={t("nav.backToTop")}
            className="sq-sm mr-2 inline-flex focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25"
            href="#top"
          >
            <Logo asLink={false} className="h-5" />
          </a>
          <ul className="hidden items-center gap-1 md:flex">
            {navLinks.map((link) => (
              <li key={link.id}>
                <a
                  aria-current={active === link.id ? "location" : undefined}
                  className={cn(
                    "sq-sm inline-flex min-h-9 items-center px-3 text-sm font-semibold text-muted-foreground hover:bg-secondary hover:text-foreground",
                    "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25",
                    "aria-[current=location]:bg-accent aria-[current=location]:text-accent-foreground",
                    fluid,
                  )}
                  href={`#${link.id}`}
                >
                  {t(link.label)}
                </a>
              </li>
            ))}
          </ul>
          <LanguageMenu />
          <div className="hidden md:block">
            <Appearance />
          </div>
          <SquircleButton asChild className="hidden sm:inline-flex" size="sm">
            <RouterLink to="/">{t("nav.ask")}</RouterLink>
          </SquircleButton>
          <button
            aria-controls="landing-menu"
            aria-expanded={open}
            aria-label={open ? t("nav.closeMenu") : t("nav.openMenu")}
            className="sq-sm relative grid size-10 place-items-center text-foreground hover:bg-secondary focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25 md:hidden"
            onClick={() => setOpen((value) => !value)}
            type="button"
          >
            <span
              aria-hidden
              className={cn(
                "absolute h-0.5 w-5 bg-current",
                fluid,
                open ? "translate-y-0 rotate-45" : "-translate-y-1",
              )}
            />
            <span
              aria-hidden
              className={cn(
                "absolute h-0.5 w-5 bg-current",
                fluid,
                open ? "translate-y-0 -rotate-45" : "translate-y-1",
              )}
            />
          </button>
        </nav>
      </header>

      <div
        aria-hidden={!open}
        className={cn(
          "fixed inset-0 z-40 bg-background/80 backdrop-blur-3xl md:hidden",
          fluid,
          open ? "visible opacity-100" : "invisible opacity-0",
        )}
        id="landing-menu"
        inert={!open}
      >
        <ul className="flex h-full flex-col justify-center gap-2 px-8">
          {[...navLinks, { id: "start", label: "nav.ask" } as const].map(
            (link, index) => (
              <li
                className={cn(
                  fluid,
                  open
                    ? "translate-y-0 opacity-100"
                    : "translate-y-12 opacity-0",
                )}
                key={link.id}
                style={{
                  transitionDelay: open ? `${100 + index * 50}ms` : "0ms",
                }}
              >
                <a
                  className="sq-sm block py-3 font-display text-title-2 text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25"
                  href={`#${link.id}`}
                  onClick={() => setOpen(false)}
                >
                  {t(link.label)}
                </a>
              </li>
            ),
          )}
          <li
            className={cn(
              "mt-6 [&>div]:justify-start",
              fluid,
              open ? "translate-y-0 opacity-100" : "translate-y-12 opacity-0",
            )}
            style={{ transitionDelay: open ? "300ms" : "0ms" }}
          >
            <Appearance />
          </li>
        </ul>
      </div>
    </>
  )
}

/* Shared building blocks */

function Reveal({
  children,
  className,
  delay = 0,
  as: Tag = "div",
}: {
  children: ReactNode
  className?: string
  delay?: number
  as?: "div" | "li" | "section"
}) {
  const [ref, inView] = useInView<HTMLElement>()
  return (
    <Tag
      className={cn(
        "transition-all duration-1000 ease-[cubic-bezier(0.32,0.72,0,1)]",
        inView
          ? "translate-y-0 opacity-100 blur-0"
          : "translate-y-16 opacity-0 blur-md",
        className,
      )}
      ref={ref as never}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </Tag>
  )
}

function SectionIntro({
  kicker,
  title,
  children,
  id,
  className,
}: {
  kicker: string
  title: ReactNode
  children?: ReactNode
  id?: string
  className?: string
}) {
  return (
    <Reveal className={cn("max-w-[680px]", className)}>
      <p className="mb-3 text-overline uppercase text-primary">{kicker}</p>
      <h2
        className="font-display text-title-2 text-balance text-foreground sm:text-title-1"
        id={id}
      >
        {title}
      </h2>
      {children ? (
        <p className="mt-4 text-body-lg text-pretty text-muted-foreground">
          {children}
        </p>
      ) : null}
    </Reveal>
  )
}

function QuestionForm({ className, ...props }: ComponentProps<"form">) {
  const { t } = useTranslation("landing")
  const navigate = useNavigate()
  const [question, setQuestion] = useState("")
  const [error, setError] = useState<string | null>(null)
  const inputId = useId()
  const errorId = useId()

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const value = question.trim()
    if (!value) {
      setError(t("form.empty"))
      return
    }
    if (value.length > 2000) {
      setError(t("form.tooLong"))
      return
    }
    void navigate({ to: "/", search: { q: value } })
  }

  return (
    <form
      className={cn("w-full", className)}
      noValidate
      onSubmit={submit}
      {...props}
    >
      <label className="sr-only" htmlFor={inputId}>
        {t("form.label")}
      </label>
      <div
        className={cn(
          "sq-lg flex flex-col gap-2 border bg-card p-2 shadow-[var(--shadow-soft)] sm:flex-row sm:items-center",
          "focus-within:border-primary/45 focus-within:ring-[3px] focus-within:ring-ring/20",
          error ? "border-[color:var(--legal-red)]/45" : "border-border",
          fluid,
        )}
      >
        <div className="flex min-w-0 flex-1 items-center gap-3 px-3">
          <FiSearch
            aria-hidden
            className="size-4 shrink-0 text-muted-foreground"
          />
          <input
            aria-describedby={error ? errorId : undefined}
            aria-invalid={error ? true : undefined}
            autoComplete="off"
            className="min-h-11 w-full min-w-0 bg-transparent text-body-lg text-foreground placeholder:text-muted-foreground focus:outline-none"
            id={inputId}
            maxLength={2000}
            name="q"
            onChange={(event) => {
              setQuestion(event.target.value)
              if (error) setError(null)
            }}
            placeholder={t("form.placeholder")}
            value={question}
          />
        </div>
        <SquircleButton
          className="active:scale-[0.98] sm:shrink-0"
          size="lg"
          type="submit"
        >
          {t("form.submit")}
          <FiArrowRight aria-hidden className="size-4" />
        </SquircleButton>
      </div>
      {error ? (
        <p
          className="mt-2 px-2 text-label font-normal text-[color:var(--legal-red)]"
          id={errorId}
          role="alert"
        >
          {error}
        </p>
      ) : null}
    </form>
  )
}

function QuestionLink({
  question,
  className,
}: {
  question: string
  className?: string
}) {
  return (
    <RouterLink
      className={cn(
        "sq-sm inline-flex items-center gap-2 border border-border bg-card/60 px-3 py-2 text-left text-sm font-medium text-muted-foreground",
        "hover:-translate-y-0.5 hover:border-primary/30 hover:bg-accent hover:text-accent-foreground active:translate-y-0",
        "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25",
        fluid,
        className,
      )}
      search={{ q: question }}
      to="/"
    >
      {question}
    </RouterLink>
  )
}

/* Hero */

function Hero() {
  const { t } = useTranslation("landing")
  return (
    <section
      aria-labelledby="hero-title"
      className="mx-auto grid w-full max-w-7xl gap-12 px-4 pb-20 pt-32 sm:px-6 sm:pt-40 lg:grid-cols-[minmax(0,680px)_minmax(0,1fr)] lg:items-center lg:gap-12 lg:pb-24"
    >
      <div className="min-w-0">
        <Reveal>
          <p className="mb-4 text-overline uppercase text-primary">
            {t("hero.kicker")}
          </p>
          <h1
            className="max-w-[680px] font-display text-title-1 text-balance text-foreground sm:text-display"
            id="hero-title"
          >
            <span className="block text-balance">{t("hero.line1")}</span>
            <span className="block text-balance">{t("hero.line2")}</span>
          </h1>
          <p className="mt-6 max-w-[680px] text-body-lg text-pretty text-muted-foreground">
            {t("hero.body")}
          </p>
        </Reveal>
        <Reveal className="mt-8" delay={120}>
          <QuestionForm id="start" />
          <ul
            aria-label={t("hero.pointsLabel")}
            className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-label font-normal text-muted-foreground"
          >
            {(t("hero.points", { returnObjects: true }) as string[]).map(
              (item) => (
                <li className="flex items-center gap-1.5" key={item}>
                  <FiCheckCircle
                    aria-hidden
                    className="size-3.5 text-primary"
                  />
                  {item}
                </li>
              ),
            )}
          </ul>
        </Reveal>
      </div>
      <Reveal className="min-w-0" delay={240}>
        <AnswerPreview />
      </Reveal>
    </section>
  )
}

function AnswerPreview() {
  const { t } = useTranslation("landing")
  return (
    <figure
      aria-label={t("preview.label")}
      className="sq-xxl border border-border bg-secondary/70 p-3 shadow-[var(--shadow-soft)] sm:p-4"
    >
      <div className="flex justify-end">
        <p className="sq-lg max-w-[85%] bg-primary px-4 py-3 text-body text-primary-foreground">
          {t("preview.question")}
        </p>
      </div>
      <div className="sq-xl mt-3 border border-border bg-card p-5">
        <p className="text-body-lg text-foreground">{t("preview.answer")}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {["Section 37", "Section 45"].map((label) => (
            <span
              className="sq-xs inline-flex min-h-7 items-center border border-[color:var(--legal-blue)]/15 bg-[color:var(--legal-blue-soft)] px-2 text-xs font-bold text-[color:var(--legal-blue)]"
              key={label}
            >
              {label}
            </span>
          ))}
        </div>
        <div className="sq-lg mt-5 border border-border bg-background/60 p-4">
          <p className="text-label text-primary">{t("preview.sectionTitle")}</p>
          <blockquote
            lang="en"
            className="mt-2 border-l-2 border-primary/35 pl-3 font-legal text-statute-sm text-foreground/90"
          >
            The privacy of citizens, their homes, correspondence, telephone
            conversations and telegraphic communications is hereby guaranteed
            and protected.
          </blockquote>
        </div>
        <p className="mt-4 flex gap-2 text-label font-normal text-muted-foreground">
          <FiInfo aria-hidden className="mt-0.5 size-4 shrink-0" />
          <span>{t("preview.edition")}</span>
        </p>
      </div>
    </figure>
  )
}

/* Problem to solution */

function ProblemSection() {
  const { t } = useTranslation("landing")
  return (
    <section
      aria-labelledby="problem-title"
      className="mx-auto w-full max-w-7xl px-4 py-20 sm:px-6"
    >
      <SectionIntro
        id="problem-title"
        kicker={t("problem.kicker")}
        title={t("problem.title")}
      >
        {t("problem.body")}
      </SectionIntro>
      <div className="mt-12 grid gap-4 md:grid-cols-2">
        <Reveal className="sq-xl border border-border bg-card p-6 sm:p-8">
          <p className="text-overline uppercase text-muted-foreground">
            {t("problem.pdfKicker")}
          </p>
          <p className="mt-4 font-display text-title-3 text-foreground">
            {t("problem.pdfTitle")}
          </p>
          <p className="mt-3 text-body text-muted-foreground">
            {t("problem.pdfBody")}
          </p>
        </Reveal>
        <Reveal
          className="sq-xl border border-primary/30 bg-accent p-6 sm:p-8"
          delay={120}
        >
          <p className="text-overline uppercase text-accent-foreground">
            {t("problem.appKicker")}
          </p>
          <p className="mt-4 font-display text-title-3 text-foreground">
            {t("problem.appTitle")}
          </p>
          <p className="mt-3 text-body text-accent-foreground">
            {t("problem.appBody")}
          </p>
        </Reveal>
      </div>
    </section>
  )
}

/* Tagline reveal */

function TaglineReveal() {
  const { t } = useTranslation("landing")
  const taglineLines = t("tagline", { returnObjects: true }) as string[]
  const containerRef = useRef<HTMLHeadingElement | null>(null)
  const [lit, setLit] = useState<Set<number>>(() => new Set())

  useEffect(() => {
    const node = containerRef.current
    if (!node) return
    const words = [...node.querySelectorAll<HTMLElement>("[data-word]")]
    if (typeof IntersectionObserver === "undefined") {
      setLit(new Set(words.map((_, index) => index)))
      return
    }
    // Trigger line at 60% of the viewport: words above it are lit.
    const observer = new IntersectionObserver(
      (entries) => {
        setLit((current) => {
          const next = new Set(current)
          for (const entry of entries) {
            const index = Number((entry.target as HTMLElement).dataset.word)
            const bottom = entry.rootBounds?.bottom ?? window.innerHeight * 0.6
            if (entry.boundingClientRect.top < bottom) next.add(index)
            else next.delete(index)
          }
          return next
        })
      },
      { rootMargin: "0px 0px -40% 0px", threshold: [0, 1] },
    )
    for (const word of words) observer.observe(word)
    return () => observer.disconnect()
  }, [])

  let index = 0
  return (
    <section className="bg-card py-24 sm:py-32">
      <div className="mx-auto w-full max-w-7xl px-4 sm:px-6">
        <h2
          className="max-w-[680px] font-display text-title-1 text-balance sm:text-display"
          ref={containerRef}
        >
          {taglineLines.map((line) => (
            <span className="block" key={line}>
              {line.split(" ").map((word) => {
                const position = index++
                return (
                  <span key={`${line}-${position}`}>
                    <span
                      className={cn(
                        "transition-colors duration-700 ease-[cubic-bezier(0.32,0.72,0,1)]",
                        lit.has(position)
                          ? "text-foreground"
                          : "text-foreground/30",
                      )}
                      data-word={position}
                    >
                      {word}
                    </span>{" "}
                  </span>
                )
              })}
            </span>
          ))}
        </h2>
      </div>
    </section>
  )
}

/* Benefits */

const benefitIcons = [FiMessageCircle, FiCheckCircle, FiBookOpen, FiBookmark]

type Copy = { title: string; body: string }

function Benefits() {
  const { t } = useTranslation("landing")
  const benefits = (t("benefits.items", { returnObjects: true }) as Copy[]).map(
    (item, position) => ({ ...item, icon: benefitIcons[position] }),
  )
  return (
    <section
      aria-labelledby="benefits-title"
      className="mx-auto w-full max-w-7xl px-4 py-24 sm:px-6"
    >
      <SectionIntro
        id="benefits-title"
        kicker={t("benefits.kicker")}
        title={t("benefits.title")}
      />
      <ul className="mt-12 grid gap-4 sm:grid-cols-2">
        {benefits.map((benefit, position) => (
          <Reveal
            as="li"
            className="sq-xl border border-border bg-card p-6"
            delay={position * 80}
            key={benefit.title}
          >
            <span className="sq-md grid size-11 place-items-center bg-accent text-accent-foreground">
              <benefit.icon aria-hidden className="size-5" />
            </span>
            <h3 className="mt-5 font-display text-title-3 text-foreground">
              {benefit.title}
            </h3>
            <p className="mt-2 text-body text-pretty text-muted-foreground">
              {benefit.body}
            </p>
          </Reveal>
        ))}
      </ul>
    </section>
  )
}

/* How it works */

function HowItWorks() {
  const { t } = useTranslation("landing")
  const steps = t("steps.items", { returnObjects: true }) as Copy[]
  return (
    <section
      aria-labelledby="how-it-works-title"
      className="scroll-mt-24 border-y border-border bg-card"
      id="how-it-works"
    >
      <div className="mx-auto w-full max-w-7xl px-4 py-24 sm:px-6">
        <SectionIntro
          id="how-it-works-title"
          kicker={t("steps.kicker")}
          title={t("steps.title")}
        />
        <ol className="mt-12 grid gap-4 md:grid-cols-3">
          {steps.map((step, position) => (
            <Reveal
              as="li"
              className="sq-xl border border-border bg-background p-6"
              delay={position * 100}
              key={step.title}
            >
              <span className="font-mono text-code text-primary">
                0{position + 1}
              </span>
              <h3 className="mt-4 font-display text-title-3 text-foreground">
                {step.title}
              </h3>
              <p className="mt-2 text-body text-pretty text-muted-foreground">
                {step.body}
              </p>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  )
}

/* Proof */

function Proof() {
  const { t } = useTranslation("landing")
  const stats = t("proof.stats", { returnObjects: true }) as {
    value: string
    label: string
  }[]
  return (
    <section
      aria-labelledby="examples-title"
      className="mx-auto w-full max-w-7xl scroll-mt-24 px-4 py-24 sm:px-6"
      id="examples"
    >
      <SectionIntro
        id="examples-title"
        kicker={t("proof.kicker")}
        title={t("proof.title")}
      >
        {t("proof.body")}
      </SectionIntro>
      <dl className="mt-12 grid gap-4 md:grid-cols-3">
        {stats.map((stat, position) => (
          <Reveal
            className="sq-xl border border-border bg-card p-6"
            delay={position * 100}
            key={stat.value}
          >
            <dt className="sr-only">{stat.label}</dt>
            <dd>
              <span className="block font-display text-title-1 text-primary">
                {stat.value}
              </span>
              <span className="mt-2 block text-body text-pretty text-muted-foreground">
                {stat.label}
              </span>
            </dd>
          </Reveal>
        ))}
      </dl>
      <p className="mt-6 text-body text-muted-foreground">
        <Trans
          components={{
            methodology: (
              <RouterLink
                className="text-primary underline"
                to="/methodology"
              />
            ),
          }}
          i18nKey="proof.limits"
          ns="landing"
        />
      </p>
      <Reveal className="mt-16">
        <h3 className="text-overline uppercase text-muted-foreground">
          {t("proof.try")}
        </h3>
        <ul className="mt-4 flex flex-wrap gap-2">
          {(t("proof.examples", { returnObjects: true }) as string[]).map(
            (question) => (
              <li key={question}>
                <QuestionLink question={question} />
              </li>
            ),
          )}
        </ul>
      </Reveal>
    </section>
  )
}

/* FAQ */

function Faq() {
  const { t } = useTranslation("landing")
  const faqs = t("faq.items", { returnObjects: true }) as {
    q: string
    a: string
  }[]
  return (
    <section
      aria-labelledby="faq-title"
      className="scroll-mt-24 border-y border-border bg-card"
      id="faq"
    >
      <div className="mx-auto grid w-full max-w-7xl gap-12 px-4 py-24 sm:px-6 lg:grid-cols-[1fr_1.4fr]">
        <SectionIntro
          className="lg:sticky lg:top-32 lg:self-start"
          id="faq-title"
          kicker={t("faq.kicker")}
          title={t("faq.title")}
        >
          {t("faq.body")}
        </SectionIntro>
        <div className="grid gap-3">
          {faqs.map((item, position) => (
            <Reveal delay={Math.min(position, 4) * 60} key={item.q}>
              <details className="group sq-lg border border-border bg-background open:border-primary/30">
                <summary
                  className={cn(
                    "sq-lg flex cursor-pointer list-none items-center justify-between gap-4 p-5 text-body-lg font-semibold text-foreground hover:text-accent-foreground",
                    "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25 [&::-webkit-details-marker]:hidden",
                    fluid,
                  )}
                >
                  {item.q}
                  <FiChevronDown
                    aria-hidden
                    className={cn(
                      "size-4 shrink-0 text-muted-foreground group-open:rotate-180",
                      fluid,
                    )}
                  />
                </summary>
                <p className="px-5 pb-5 text-body text-pretty text-muted-foreground">
                  {item.a}
                </p>
              </details>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}

/* Final call to action */

function FinalCta() {
  const { t } = useTranslation("landing")
  return (
    <section
      aria-labelledby="final-title"
      className="mx-auto w-full max-w-7xl px-4 py-24 sm:px-6 sm:py-32"
    >
      <Reveal className="mx-auto flex max-w-[680px] flex-col items-center text-center">
        <p className="mb-3 text-overline uppercase text-primary">
          {t("final.kicker")}
        </p>
        <h2
          className="font-display text-title-2 text-balance text-foreground sm:text-title-1"
          id="final-title"
        >
          {t("final.title")}
        </h2>
        <p className="mt-4 text-body-lg text-pretty text-muted-foreground">
          {t("final.body")}
        </p>
        <QuestionForm className="mt-8 text-left" />
        <RouterLink
          className="sq-sm mt-6 inline-flex items-center gap-1.5 px-2 py-1 text-sm font-semibold text-[color:var(--legal-blue)] hover:underline focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25"
          to="/laws"
        >
          {t("final.browse")}
          <FiArrowRight aria-hidden className="size-3.5" />
        </RouterLink>
      </Reveal>
    </section>
  )
}

/* Footer */

const footerLinks = [
  { label: "ask", to: "/" },
  { label: "about", to: "/about" },
  { label: "methodology", to: "/methodology" },
  { label: "laws", to: "/laws" },
  { label: "saved", to: "/saved" },
  { label: "login", to: "/login" },
  { label: "privacy", to: "/privacy" },
] as const

function SiteFooter() {
  const { t } = useTranslation("landing")
  return (
    <footer className="border-t border-border bg-sidebar">
      <div className="mx-auto grid w-full max-w-7xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_1fr]">
        <div>
          <Logo asLink={false} className="h-5" />
          <p className="mt-4 max-w-md text-body text-pretty text-muted-foreground">
            {t("footer.about")}
          </p>
        </div>
        <nav aria-label={t("footer.label")}>
          <ul className="grid gap-2 sm:grid-cols-2">
            {footerLinks.map((link) => (
              <li key={link.to}>
                <RouterLink
                  className="sq-xs text-body text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25"
                  to={link.to}
                >
                  {t(`footer.links.${link.label}`)}
                </RouterLink>
              </li>
            ))}
          </ul>
        </nav>
      </div>
      <div className="border-t border-border">
        <p className="mx-auto w-full max-w-7xl px-4 py-4 text-label font-normal text-muted-foreground sm:px-6">
          constitution.ng · {new Date().getFullYear()}
        </p>
      </div>
    </footer>
  )
}
