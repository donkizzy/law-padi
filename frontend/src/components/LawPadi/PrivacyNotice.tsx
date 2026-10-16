import { Link } from "@tanstack/react-router"
import type { ReactNode } from "react"

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

export function PrivacyNotice() {
  return (
    <article className="mx-auto grid max-w-3xl gap-10 px-4 py-8 sm:px-8 lg:py-12">
      <SectionHeading kicker="Privacy" title="How we handle your data.">
        What constitution.ng keeps, why, for how long, and what you can do about
        it. Last updated 16 October 2026.
      </SectionHeading>

      <Section title="You don't need an account">
        <p>
          You can ask questions, browse the Constitution and save sections
          without signing up. An account only adds one thing: your conversations
          and saved sections follow you to any device.
        </p>
      </Section>

      <Section title="What we keep">
        <ul className="grid list-disc gap-2 pl-5">
          <li>
            <strong className="text-foreground">
              Your questions and answers.
            </strong>{" "}
            Conversations are stored so you can come back to them. If you're a
            guest, they're tied to a cookie on this browser.
          </li>
          <li>
            <strong className="text-foreground">
              Your account, if you make one.
            </strong>{" "}
            Your email address, your name if you give it, and your password,
            stored only as a one-way hash we can't read.
          </li>
          <li>
            <strong className="text-foreground">
              Saved sections and preferences.
            </strong>{" "}
            Kept on your browser. Once you confirm your email, they're also kept
            in your account.
          </li>
          <li>
            <strong className="text-foreground">
              Feedback you choose to give
            </strong>{" "}
            on an answer.
          </li>
          <li>
            <strong className="text-foreground">Security records.</strong> A
            sign-in cookie, and short-lived counts of sign-in attempts keyed to
            a scrambled form of your IP address or email, so we can stop people
            guessing passwords.
          </li>
        </ul>
        <p>
          Please don't put personal details in your questions that you don't
          need to. Ask about the situation, not the names.
        </p>
      </Section>

      <Section title="Why we keep it">
        <p>
          Only to run the service you asked for: answering your questions,
          keeping your research, signing you in safely, and fixing problems. We
          don't sell your data or use it for advertising.
        </p>
      </Section>

      <Section title="Who else handles it">
        <ul className="grid list-disc gap-2 pl-5">
          <li>
            <strong className="text-foreground">Cloudflare</strong> delivers the
            website and passes your requests to our servers.
          </li>
          <li>
            <strong className="text-foreground">Render</strong> runs our servers
            in the United States.
          </li>
          <li>
            <strong className="text-foreground">Neon</strong> stores our
            database.
          </li>
          <li>
            <strong className="text-foreground">DeepSeek</strong> receives your
            question and the relevant parts of the Constitution when
            plain-English explanations are switched on, so it can write the
            explanation. It doesn't receive your name, email or account details.
          </li>
          <li>
            <strong className="text-foreground">Our email provider</strong>{" "}
            sends sign-up and password emails to your address.
          </li>
        </ul>
        <p>
          Some of these services are outside Nigeria, so your data may be
          processed abroad. We only share what each service needs to do its job.
        </p>
      </Section>

      <Section title="How long we keep it">
        <ul className="grid list-disc gap-2 pl-5">
          <li>Guest conversations are deleted after 30 days without use.</li>
          <li>
            Account conversations, saved sections and preferences are kept until
            you delete them or your account.
          </li>
          <li>
            Sign-in sessions end after 30 days without use, or when you sign
            out. Sign-in attempt counts are cleared within a day.
          </li>
        </ul>
      </Section>

      <Section title="Your rights">
        <p>
          Under the Nigeria Data Protection Act 2023 you can ask to see,
          correct, move or delete your data, object to how we use it, and
          withdraw your consent. Most of this you can do yourself:
        </p>
        <ul className="grid list-disc gap-2 pl-5">
          <li>
            Download everything your account holds, or delete your account, in{" "}
            <Link
              className="font-semibold text-primary underline"
              to="/settings"
            >
              Settings
            </Link>
            .
          </li>
          <li>Change your name or email in Settings.</li>
          <li>Delete any conversation from the conversation list.</li>
          <li>
            Clear what's saved on this browser in Settings, under Security.
          </li>
        </ul>
        <p>
          {contactEmail ? (
            <>
              For anything else, email{" "}
              <a
                className="font-semibold text-primary underline"
                href={`mailto:${contactEmail}`}
              >
                {contactEmail}
              </a>
              .{" "}
            </>
          ) : null}
          If you're unhappy with how we've handled your data, you can complain
          to the{" "}
          <a
            className="font-semibold text-primary underline"
            href="https://ndpc.gov.ng"
            rel="noreferrer"
            target="_blank"
          >
            Nigeria Data Protection Commission
          </a>
          .
        </p>
      </Section>
    </article>
  )
}
