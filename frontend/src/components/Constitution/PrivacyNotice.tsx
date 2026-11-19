import { Link } from "@tanstack/react-router"
import type { ReactNode } from "react"
import { Trans, useTranslation } from "react-i18next"

import { SectionHeading } from "./primitives"

const contactEmail = import.meta.env.VITE_PRIVACY_CONTACT_EMAIL

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="grid gap-3">
      <h2 className="font-display text-title-3 text-foreground">{title}</h2>
      <div className="grid gap-3 text-body text-muted-foreground">
        {children}
      </div>
    </section>
  )
}

const strong = <strong className="text-foreground" />
const link = "font-semibold text-primary underline"

/** List items from the catalogue; `<strong>` marks the lead-in. */
function Items({ keys }: { keys: string[] }) {
  return (
    <ul className="grid list-disc gap-2 pl-5">
      {keys.map((key) => (
        <li key={key}>
          <Trans
            components={{
              strong,
              settings: <Link className={link} to="/settings" />,
            }}
            i18nKey={key as never}
            ns="privacy"
          />
        </li>
      ))}
    </ul>
  )
}

export function PrivacyNotice() {
  const { t } = useTranslation("privacy")
  return (
    <article className="mx-auto grid max-w-3xl gap-10 px-4 py-8 sm:px-8 lg:py-12">
      <SectionHeading kicker={t("kicker")} title={t("title")}>
        {t("intro")}
      </SectionHeading>

      <Section title={t("noAccount.title")}>
        <p>{t("noAccount.body")}</p>
      </Section>

      <Section title={t("keep.title")}>
        <Items
          keys={[
            "keep.questions",
            "keep.account",
            "keep.saved",
            "keep.feedback",
            "keep.security",
          ]}
        />
        <p>{t("keep.advice")}</p>
      </Section>

      <Section title={t("why.title")}>
        <p>{t("why.body")}</p>
      </Section>

      <Section title={t("processors.title")}>
        <Items
          keys={[
            "processors.cloudflare",
            "processors.railway",
            "processors.deepseek",
            "processors.email",
          ]}
        />
        <p>{t("processors.abroad")}</p>
      </Section>

      <Section title={t("retention.title")}>
        <Items
          keys={["retention.guest", "retention.account", "retention.sessions"]}
        />
      </Section>

      <Section title={t("rights.title")}>
        <p>{t("rights.body")}</p>
        <Items
          keys={[
            "rights.download",
            "rights.change",
            "rights.delete",
            "rights.clear",
          ]}
        />
        <p>
          {contactEmail ? (
            <>
              <Trans
                components={{
                  // Trans swaps in the catalogue's link text.
                  email: (
                    <a className={link} href={`mailto:${contactEmail}`}>
                      {contactEmail}
                    </a>
                  ),
                }}
                i18nKey="rights.contact"
                ns="privacy"
                values={{ email: contactEmail }}
              />{" "}
            </>
          ) : null}
          <Trans
            components={{
              ndpc: (
                <a
                  className={link}
                  href="https://ndpc.gov.ng"
                  rel="noreferrer"
                  target="_blank"
                >
                  NDPC
                </a>
              ),
            }}
            i18nKey="rights.complain"
            ns="privacy"
          />
        </p>
      </Section>
    </article>
  )
}
