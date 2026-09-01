import { Link as RouterLink } from "@tanstack/react-router"
import { useMemo, useState } from "react"
import { FiArrowLeft, FiCopy, FiShare2 } from "react-icons/fi"

import { ChatComposer } from "@/components/LawPadi/ChatComposer"
import {
  AmendmentTimeline,
  CitationChip,
  InlineAction,
  OfficialTextBlock,
  SectionHeading,
  SquircleButton,
  StatusBadge,
  TranslationBlock,
} from "@/components/LawPadi/primitives"
import { SourcePanel } from "@/components/LawPadi/SourcePanel"
import { defaultProvision, provisions } from "@/lib/law-padi-data"

export function ProvisionDetail({ sectionId }: { sectionId?: string }) {
  const [question, setQuestion] = useState("")
  const [sourceOpen, setSourceOpen] = useState(false)

  const provision = useMemo(
    () =>
      provisions.find((candidate) => candidate.id === sectionId) ??
      defaultProvision,
    [sectionId],
  )

  return (
    <div
      className={
        sourceOpen ? "grid xl:grid-cols-[minmax(0,1fr)_380px]" : "grid"
      }
    >
      <section className="min-w-0 px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
        <div className="mx-auto w-full max-w-4xl">
          <RouterLink
            className="sq-sm mb-7 inline-flex min-h-10 items-center gap-2 px-2 text-sm font-semibold text-muted-foreground transition hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25"
            to="/constitution"
          >
            <FiArrowLeft className="size-4" aria-hidden />
            Back to browse
          </RouterLink>

          <SectionHeading
            action={<StatusBadge status={provision.status} />}
            kicker={`${provision.section} - ${provision.chapter}`}
            title={`${provision.title}.`}
          >
            {provision.sourceTitle}
          </SectionHeading>

          <div className="grid gap-5">
            <OfficialTextBlock>{provision.officialText}</OfficialTextBlock>

            <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
              <section className="sq-lg border border-border bg-card p-5">
                <h2 className="mb-3 text-[0.72rem] font-bold uppercase text-muted-foreground">
                  Plain-language explanation
                </h2>
                <p className="text-sm leading-7 text-muted-foreground">
                  {provision.summary} Ask follow-up questions in everyday
                  language and the answer should still point back to a verified
                  provision, version and source.
                </p>
              </section>

              <section className="sq-lg border border-border bg-card p-5">
                <h2 className="mb-3 text-[0.72rem] font-bold uppercase text-muted-foreground">
                  Citation and source
                </h2>
                <div className="grid gap-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground">Citation</span>
                    <CitationChip onClick={() => setSourceOpen(true)}>
                      {provision.citation}
                    </CitationChip>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground">Source</span>
                    <span className="text-right font-semibold text-foreground">
                      {provision.sourceAuthority}
                    </span>
                  </div>
                </div>
                <SquircleButton
                  className="mt-5 w-full"
                  onClick={() => setSourceOpen(true)}
                  type="button"
                  variant="outline"
                >
                  Open source inspector
                </SquircleButton>
              </section>
            </div>

            <TranslationBlock />

            <section className="sq-lg border border-border bg-card p-5">
              <h2 className="mb-4 text-[0.72rem] font-bold uppercase text-muted-foreground">
                Amendment history
              </h2>
              <AmendmentTimeline events={provision.history} />
            </section>

            <section className="sq-lg border border-border bg-card p-5">
              <h2 className="mb-4 text-[0.72rem] font-bold uppercase text-muted-foreground">
                Related provisions
              </h2>
              <div className="flex flex-wrap gap-2">
                {provision.related.map((related) => (
                  <InlineAction key={related} type="button">
                    {related}
                  </InlineAction>
                ))}
              </div>
            </section>

            <section className="sq-lg border border-border bg-card p-5">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="font-legal text-xl leading-tight text-foreground">
                    Ask about this section
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Answers here stay grounded in {provision.section}.
                  </p>
                </div>
                <div className="flex gap-2">
                  <SquircleButton size="sm" type="button" variant="ghost">
                    <FiCopy className="size-4" aria-hidden />
                    Copy text
                  </SquircleButton>
                  <SquircleButton size="sm" type="button" variant="ghost">
                    <FiShare2 className="size-4" aria-hidden />
                    Share
                  </SquircleButton>
                </div>
              </div>
              <ChatComposer
                compact
                contextLabel={`Grounded in ${provision.section}`}
                onChange={setQuestion}
                onSubmit={() => setQuestion("")}
                placeholder={`Ask a follow-up about ${provision.section}...`}
                value={question}
              />
            </section>
          </div>
        </div>
      </section>

      <SourcePanel
        onOpenChange={setSourceOpen}
        open={sourceOpen}
        provision={provision}
      />
    </div>
  )
}
