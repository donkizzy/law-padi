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
import { Logo } from "@/components/Common/Logo"
import { SquircleButton } from "@/components/LawPadi/primitives"
import { useInView } from "@/hooks/useInView"
import { cn } from "@/lib/utils"

// Heavy, springy motion used by every landing transition.
const fluid = "transition-all duration-700 ease-[cubic-bezier(0.32,0.72,0,1)]"

const navLinks = [
  { id: "how-it-works", label: "How it works" },
  { id: "examples", label: "What people ask" },
  { id: "faq", label: "Questions" },
]

export const exampleQuestions = [
  "Can police search my phone?",
  "How long can police hold me before court?",
  "Who can run for president?",
  "Can I own land in another state?",
  "wetin constitution talk about freedom of religion?",
  "What does Section 33 say?",
]

export const faqs = [
  {
    q: "Is this legal advice?",
    a: "No. constitution.ng explains what the Constitution says and shows you the exact section. If you are facing a court case, an arrest or a dispute, speak to a lawyer or the Legal Aid Council. Bring the sections you found here with you.",
  },
  {
    q: "Is it free?",
    a: "Yes. Asking questions, finding sections and reading the full Constitution are free. There is no paid plan.",
  },
  {
    q: "Do I need an account?",
    a: "No. You can ask and read as a guest. Create an account only if you want your conversations to follow you to another device.",
  },
  {
    q: "Is this the current Constitution?",
    a: "It is the 1999 Constitution as published in 2004. Amendments passed after that are not included yet, so a section may have changed since. Every answer tells you this so you can check before you rely on it.",
  },
  {
    q: "Can I ask in Pidgin?",
    a: "Yes. Ask the way you would say it, in English or Pidgin, and we will find the section. Answers are written in plain English, and the official wording is always the English text.",
  },
  {
    q: "How do you choose the section?",
    a: "Your question is matched against every section, using both the words you typed and what you mean. Citations come from the text itself, never guessed, and every answer lists the sections it used so you can read them yourself.",
  },
  {
    q: "Can I quote an answer?",
    a: "Yes. Copy any answer with its citations, or save the sections you need. Quote the official wording, not the explanation, when accuracy matters.",
  },
  {
    q: "Is this a government website?",
    a: "No. constitution.ng is independent. It is not published by, or connected to, the National Assembly or any government body.",
  },
]

export function LandingPage() {
  return (
    <div className="min-h-svh bg-background text-foreground" id="top">
      <a
        className="sq-sm fixed left-4 top-4 z-[60] -translate-y-24 bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground focus-visible:translate-y-0 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25"
        href="#main"
      >
        Skip to content
      </a>
      <IslandNav />
      <main id="main">
        <Hero />
        <ProblemSection />
        <TaglineReveal />
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
          aria-label="Main"
          className={cn(
            "sq-lg pointer-events-auto mx-auto mt-6 flex w-full max-w-max items-center gap-2 border border-border bg-card/75 py-2 pl-4 pr-2 shadow-[var(--shadow-subtle)] backdrop-blur-xl",
            fluid,
          )}
        >
          <a
            aria-label="constitution.ng, back to top"
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
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
          <div className="hidden md:block">
            <Appearance />
          </div>
          <SquircleButton asChild className="hidden sm:inline-flex" size="sm">
            <RouterLink to="/">Ask a question</RouterLink>
          </SquircleButton>
          <button
            aria-controls="landing-menu"
            aria-expanded={open}
            aria-label={open ? "Close menu" : "Open menu"}
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
          {[...navLinks, { id: "start", label: "Ask a question" }].map(
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
                  {link.label}
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
  const navigate = useNavigate()
  const [question, setQuestion] = useState("")
  const [error, setError] = useState<string | null>(null)
  const inputId = useId()
  const errorId = useId()

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const value = question.trim()
    if (!value) {
      setError("Type a question or a section number first.")
      return
    }
    if (value.length > 2000) {
      setError("Keep your question under 2,000 characters.")
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
        Your question about the Constitution
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
            placeholder="Can police search my phone?"
            value={question}
          />
        </div>
        <SquircleButton
          className="active:scale-[0.98] sm:shrink-0"
          size="lg"
          type="submit"
        >
          Get my answer
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
  return (
    <section
      aria-labelledby="hero-title"
      className="mx-auto grid w-full max-w-7xl gap-12 px-4 pb-20 pt-32 sm:px-6 sm:pt-40 lg:grid-cols-[minmax(0,680px)_minmax(0,1fr)] lg:items-center lg:gap-12 lg:pb-24"
    >
      <div className="min-w-0">
        <Reveal>
          <p className="mb-4 text-overline uppercase text-primary">
            Nigeria&apos;s Constitution, in plain English
          </p>
          <h1
            className="max-w-[680px] font-display text-title-1 text-balance text-foreground sm:text-display"
            id="hero-title"
          >
            <span className="block text-balance">Ask about your rights.</span>
            <span className="block text-balance">Get the exact section.</span>
          </h1>
          <p className="mt-6 max-w-[680px] text-body-lg text-pretty text-muted-foreground">
            Type your question the way you would say it. We find the part of the
            Constitution that answers it, explain it in plain English and show
            you the official wording beside it.
          </p>
        </Reveal>
        <Reveal className="mt-8" delay={120}>
          <QuestionForm id="start" />
          <ul
            aria-label="Free to use"
            className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-label font-normal text-muted-foreground"
          >
            {[
              "Free to use",
              "No account needed",
              "Every answer cites its section",
            ].map((item) => (
              <li className="flex items-center gap-1.5" key={item}>
                <FiCheckCircle aria-hidden className="size-3.5 text-primary" />
                {item}
              </li>
            ))}
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
  return (
    <figure
      aria-label="Example answer to the question: can police search my phone?"
      className="sq-xxl border border-border bg-secondary/70 p-3 shadow-[var(--shadow-soft)] sm:p-4"
    >
      <div className="flex justify-end">
        <p className="sq-lg max-w-[85%] bg-primary px-4 py-3 text-body text-primary-foreground">
          Can police search my phone?
        </p>
      </div>
      <div className="sq-xl mt-3 border border-border bg-card p-5">
        <p className="text-body-lg text-foreground">
          Your phone calls and messages are private under Section 37. Police can
          only override that under a law made for reasons like public safety or
          preventing crime, as Section 45 allows.
        </p>
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
          <p className="text-label text-primary">
            Section 37 · Right to private and family life
          </p>
          <blockquote className="mt-2 border-l-2 border-primary/35 pl-3 font-legal text-statute-sm text-foreground/90">
            The privacy of citizens, their homes, correspondence, telephone
            conversations and telegraphic communications is hereby guaranteed
            and protected.
          </blockquote>
        </div>
        <p className="mt-4 flex gap-2 text-label font-normal text-muted-foreground">
          <FiInfo aria-hidden className="mt-0.5 size-4 shrink-0" />
          <span>
            This is the 1999 Constitution as published in 2004. Later amendments
            aren&apos;t included yet.
          </span>
        </p>
      </div>
    </figure>
  )
}

/* Problem to solution */

function ProblemSection() {
  return (
    <section
      aria-labelledby="problem-title"
      className="mx-auto w-full max-w-7xl px-4 py-20 sm:px-6"
    >
      <SectionIntro
        id="problem-title"
        kicker="Why it is hard"
        title="The Constitution is written for lawyers. Your question is not."
      >
        It runs to 320 sections and 7 schedules of formal legal English. The
        words you would search for are rarely the words it uses.
      </SectionIntro>
      <div className="mt-12 grid gap-4 md:grid-cols-2">
        <Reveal className="sq-xl border border-border bg-card p-6 sm:p-8">
          <p className="text-overline uppercase text-muted-foreground">
            Searching the PDF
          </p>
          <p className="mt-4 font-display text-title-3 text-foreground">
            You search for “phone”. Nothing comes up.
          </p>
          <p className="mt-3 text-body text-muted-foreground">
            The section you need talks about “telephone conversations and
            telegraphic communications”, and the limits on it sit eight sections
            later.
          </p>
        </Reveal>
        <Reveal
          className="sq-xl border border-primary/30 bg-accent p-6 sm:p-8"
          delay={120}
        >
          <p className="text-overline uppercase text-accent-foreground">
            With constitution.ng
          </p>
          <p className="mt-4 font-display text-title-3 text-foreground">
            You ask “can police search my phone?”
          </p>
          <p className="mt-3 text-body text-accent-foreground">
            Section 37 comes first, Section 45 comes with it for the limits, and
            the answer explains both in two sentences.
          </p>
        </Reveal>
      </div>
    </section>
  )
}

/* Tagline reveal */

const taglineLines = [
  "The Constitution belongs to every Nigerian.",
  "Now every Nigerian can read it.",
]

function TaglineReveal() {
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

const benefits = [
  {
    icon: FiMessageCircle,
    title: "Ask in your own words",
    body: "Plain English, Pidgin or a half remembered section number. “Section thirty something about privacy” still finds Section 37.",
  },
  {
    icon: FiCheckCircle,
    title: "The answer comes first",
    body: "You get a direct reply to what you asked, then what it means for you and where the limits are. No legal jargon to decode.",
  },
  {
    icon: FiBookOpen,
    title: "The official wording, every time",
    body: "Every answer shows the exact text of the sections it relies on, with citations taken from the Constitution itself.",
  },
  {
    icon: FiBookmark,
    title: "Keep what you find",
    body: "Copy an answer with its citations, save sections for later, or open the page in the printed source to check it yourself.",
  },
]

function Benefits() {
  return (
    <section
      aria-labelledby="benefits-title"
      className="mx-auto w-full max-w-7xl px-4 py-24 sm:px-6"
    >
      <SectionIntro
        id="benefits-title"
        kicker="What you get"
        title="Answers you can understand and check"
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

const steps = [
  {
    title: "Ask your question",
    body: "Type it as you would ask a friend who knows the law. A section number works too.",
  },
  {
    title: "We find the sections",
    body: "Your question is matched against all 320 sections and 7 schedules, including the ones that limit a right.",
  },
  {
    title: "Read the answer and the source",
    body: "A short answer in plain English, with the official wording of each section right beside it.",
  },
]

function HowItWorks() {
  return (
    <section
      aria-labelledby="how-it-works-title"
      className="scroll-mt-24 border-y border-border bg-card"
      id="how-it-works"
    >
      <div className="mx-auto w-full max-w-7xl px-4 py-24 sm:px-6">
        <SectionIntro
          id="how-it-works-title"
          kicker="How it works"
          title="Three steps, about ten seconds"
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

const stats = [
  {
    value: "54 of 55",
    label:
      "everyday questions, in English and Pidgin, put the right section first in our latest test",
  },
  {
    value: "1,811",
    label: "passages of the Constitution, each linked to its printed page",
  },
  {
    value: "320",
    label: "sections and 7 schedules you can read, search and save",
  },
]

function Proof() {
  return (
    <section
      aria-labelledby="examples-title"
      className="mx-auto w-full max-w-7xl scroll-mt-24 px-4 py-24 sm:px-6"
      id="examples"
    >
      <SectionIntro
        id="examples-title"
        kicker="Built to be checked"
        title="Tested on the questions people really ask"
      >
        We measure every change against real phrasing, not legal phrasing. Here
        is where it stands today.
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
      <Reveal className="mt-16">
        <h3 className="text-overline uppercase text-muted-foreground">
          Try one of these
        </h3>
        <ul className="mt-4 flex flex-wrap gap-2">
          {exampleQuestions.map((question) => (
            <li key={question}>
              <QuestionLink question={question} />
            </li>
          ))}
        </ul>
      </Reveal>
    </section>
  )
}

/* FAQ */

function Faq() {
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
          kicker="Questions"
          title="Before you ask"
        >
          The short version: it is free, it is independent, and it always shows
          you the source.
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
  return (
    <section
      aria-labelledby="final-title"
      className="mx-auto w-full max-w-7xl px-4 py-24 sm:px-6 sm:py-32"
    >
      <Reveal className="mx-auto flex max-w-[680px] flex-col items-center text-center">
        <p className="mb-3 text-overline uppercase text-primary">
          Free, no account, nothing to install
        </p>
        <h2
          className="font-display text-title-2 text-balance text-foreground sm:text-title-1"
          id="final-title"
        >
          Ask your first question
        </h2>
        <p className="mt-4 text-body-lg text-pretty text-muted-foreground">
          Find out what the Constitution says about the thing on your mind, in
          under a minute.
        </p>
        <QuestionForm className="mt-8 text-left" />
        <RouterLink
          className="sq-sm mt-6 inline-flex items-center gap-1.5 px-2 py-1 text-sm font-semibold text-[color:var(--legal-blue)] hover:underline focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25"
          to="/constitution"
        >
          Or browse all 320 sections
          <FiArrowRight aria-hidden className="size-3.5" />
        </RouterLink>
      </Reveal>
    </section>
  )
}

/* Footer */

const footerLinks = [
  { label: "Ask a question", to: "/" },
  { label: "Browse the Constitution", to: "/constitution" },
  { label: "Saved sections", to: "/saved" },
  { label: "Sign in", to: "/login" },
  { label: "Privacy", to: "/privacy" },
] as const

function SiteFooter() {
  return (
    <footer className="border-t border-border bg-sidebar">
      <div className="mx-auto grid w-full max-w-7xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_1fr]">
        <div>
          <Logo asLink={false} className="h-5" />
          <p className="mt-4 max-w-md text-body text-pretty text-muted-foreground">
            Nigeria&apos;s Constitution in plain English. Independent, and not a
            government publication. Explanations are not legal advice.
          </p>
        </div>
        <nav aria-label="Footer">
          <ul className="grid gap-2 sm:grid-cols-2">
            {footerLinks.map((link) => (
              <li key={link.to}>
                <RouterLink
                  className="sq-xs text-body text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25"
                  to={link.to}
                >
                  {link.label}
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
