import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"

const researchPhrases: Record<string, readonly string[]> = {
  finding: [
    "Consulting the text",
    "Tracing the provisions",
    "Turning the pages",
    "Following cross-references",
    "Finding chapter and verse",
    "Gathering the sections",
    "Connecting the dots",
    "Poring over the law",
  ],
  writing: [
    "Unpacking the clauses",
    "Making the law plain",
    "Putting pen to paper",
    "Untangling the wording",
    "Piecing it together",
    "Weighing the words",
    "Composing the explanation",
    "Bringing the provisions together",
    "Working through the provisos",
    "Distilling the details",
  ],
  checking: [
    "Checking the citations",
    "Comparing with the text",
    "Revisiting the provisions",
    "Cross-checking the wording",
    "Reviewing the explanation",
    "Checking chapter and verse",
  ],
  translating: [
    "Finding the right words",
    "Bringing the meaning home",
    "Putting it in your language",
    "Carrying the meaning across",
  ],
}

const pixels = Array.from({ length: 9 }, (_, index) => ({
  id: `pixel-${index}`,
  delay: ((index % 3) + Math.abs(Math.floor(index / 3) - 1)) * 90,
}))

export function AnswerLoading({
  progress,
  label,
}: {
  progress: string
  label: string
}) {
  const { i18n } = useTranslation()
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const started = performance.now()
    const timer = window.setInterval(
      () => setElapsed(Math.floor((performance.now() - started) / 1000)),
      1000,
    )
    return () => window.clearInterval(timer)
  }, [])

  // Keep the existing translated stage labels in non-English interfaces.
  const phrases =
    i18n.resolvedLanguage === "en" ? researchPhrases[progress] : null
  const phrase = phrases
    ? `${phrases[Math.floor(elapsed / 4) % phrases.length]}…`
    : label
  const time =
    elapsed < 60
      ? `${elapsed}s`
      : `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`

  return (
    <div role="status" className="flex min-h-6 items-center gap-3">
      <span className="sr-only">{label}</span>
      <span
        aria-hidden="true"
        className="flex min-w-0 flex-wrap items-center gap-3"
      >
        <span className="grid shrink-0 grid-cols-3 gap-0.5">
          {pixels.map((pixel) => (
            <span
              key={pixel.id}
              className="answer-loading-pixel size-1 bg-primary"
              style={{ animationDelay: `${pixel.delay}ms` }}
            />
          ))}
        </span>
        <span className="answer-loading-label text-body font-medium">
          {phrase}
        </span>
        <span className="font-mono text-label font-normal tabular-nums text-muted-foreground">
          {time}
        </span>
      </span>
    </div>
  )
}
