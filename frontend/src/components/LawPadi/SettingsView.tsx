import { type ReactNode, useState } from "react"
import type { IconType } from "react-icons"
import {
  FiBell,
  FiCheck,
  FiGlobe,
  FiKey,
  FiLock,
  FiSave,
  FiShield,
  FiUser,
} from "react-icons/fi"

import { SectionHeading, SquircleButton } from "@/components/LawPadi/primitives"
import { cn } from "@/lib/utils"

type SettingsTab = "profile" | "preferences" | "security"

const tabs: { label: string; value: SettingsTab }[] = [
  { label: "Profile", value: "profile" },
  { label: "Preferences", value: "preferences" },
  { label: "Security", value: "security" },
]

function SettingsCard({
  children,
  icon: Icon,
  title,
}: {
  children: ReactNode
  icon: IconType
  title: string
}) {
  return (
    <section className="sq-lg border border-border bg-card p-5 shadow-[var(--shadow-subtle)] sm:p-6">
      <div className="mb-5 flex items-start gap-3">
        <div className="sq-sm grid size-10 shrink-0 place-items-center bg-accent text-accent-foreground">
          <Icon className="size-4" aria-hidden />
        </div>
        <h2 className="font-legal text-xl leading-tight text-foreground">
          {title}
        </h2>
      </div>
      {children}
    </section>
  )
}

function SettingToggle({
  description,
  label,
  onChange,
  value,
}: {
  description: string
  label: string
  onChange: () => void
  value: boolean
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-t border-border py-4 first:border-t-0 first:pt-0 last:pb-0">
      <div className="min-w-0">
        <p className="text-sm font-semibold text-foreground">{label}</p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          {description}
        </p>
      </div>
      <button
        aria-checked={value}
        aria-label={`${label}: ${value ? "on" : "off"}`}
        className={cn(
          "sq-sm flex h-7 w-12 shrink-0 items-center border p-1 transition focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25",
          value
            ? "justify-end border-primary bg-primary"
            : "justify-start border-border bg-secondary",
        )}
        onClick={onChange}
        role="switch"
        type="button"
      >
        <span
          className={cn(
            "sq-xs size-5 shadow-sm transition",
            value ? "bg-primary-foreground" : "bg-muted-foreground/40",
          )}
        />
      </button>
    </div>
  )
}

export function SettingsView() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("profile")
  const [saved, setSaved] = useState(false)
  const [sourcePanel, setSourcePanel] = useState(true)
  const [plainLanguage, setPlainLanguage] = useState(true)
  const [notifications, setNotifications] = useState(false)

  return (
    <section className="px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
      <div className="mx-auto w-full max-w-4xl">
        <SectionHeading
          kicker="Workspace settings"
          title="Make Law Padi yours."
        >
          Set the language, source context and account defaults that shape your
          constitutional research workspace.
        </SectionHeading>

        <div
          aria-label="Settings sections"
          className="mb-6 flex max-w-full gap-1 overflow-x-auto border-b border-border"
          role="tablist"
        >
          {tabs.map((tab) => (
            <button
              aria-selected={activeTab === tab.value}
              className={cn(
                "sq-sm shrink-0 px-4 py-3 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25",
                activeTab === tab.value
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground",
              )}
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              role="tab"
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "profile" ? (
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
            <SettingsCard icon={FiUser} title="Profile">
              <div className="flex flex-wrap items-center gap-4 border-b border-border pb-5">
                <div className="sq-md grid size-16 place-items-center bg-primary text-lg font-bold text-primary-foreground">
                  AG
                </div>
                <div>
                  <p className="font-legal text-2xl text-foreground">
                    Amos Godwin
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    amos@example.com
                  </p>
                </div>
              </div>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="grid gap-2 text-xs font-semibold text-muted-foreground">
                  Display name
                  <input
                    className="sq-sm min-h-11 border border-input bg-background px-3 text-sm font-normal text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-ring/20"
                    defaultValue="Amos Godwin"
                    type="text"
                  />
                </label>
                <label className="grid gap-2 text-xs font-semibold text-muted-foreground">
                  Research role
                  <select
                    className="sq-sm min-h-11 border border-input bg-background px-3 text-sm font-normal text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-ring/20"
                    defaultValue="researcher"
                  >
                    <option value="researcher">Researcher</option>
                    <option value="student">Student</option>
                    <option value="practitioner">Legal practitioner</option>
                  </select>
                </label>
              </div>
            </SettingsCard>

            <SettingsCard icon={FiShield} title="Workspace status">
              <div className="grid gap-4 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">Account</span>
                  <span className="font-semibold text-primary">Preview</span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">Corpus</span>
                  <span className="font-semibold text-foreground">0.3.0</span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">Languages</span>
                  <span className="font-semibold text-foreground">5</span>
                </div>
              </div>
            </SettingsCard>
          </div>
        ) : null}

        {activeTab === "preferences" ? (
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
            <SettingsCard icon={FiGlobe} title="Answer preferences">
              <div className="grid gap-4">
                <label className="grid gap-2 text-xs font-semibold text-muted-foreground">
                  Default answer language
                  <select
                    className="sq-sm min-h-11 border border-input bg-background px-3 text-sm font-normal text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-ring/20"
                    defaultValue="auto"
                  >
                    <option value="auto">Auto-detect</option>
                    <option value="english">English</option>
                    <option value="pidgin">Pidgin</option>
                    <option value="yoruba">Yorùbá</option>
                    <option value="igbo">Igbo</option>
                    <option value="hausa">Hausa</option>
                  </select>
                </label>
                <div className="border-t border-border pt-1">
                  <SettingToggle
                    description="Keep the exact provision and source beside every answer."
                    label="Show source panel"
                    onChange={() => setSourcePanel((value) => !value)}
                    value={sourcePanel}
                  />
                  <SettingToggle
                    description="Prefer plain explanations alongside official wording."
                    label="Plain-language summary"
                    onChange={() => setPlainLanguage((value) => !value)}
                    value={plainLanguage}
                  />
                  <SettingToggle
                    description="Receive updates when saved provisions change status."
                    label="Research notifications"
                    onChange={() => setNotifications((value) => !value)}
                    value={notifications}
                  />
                </div>
              </div>
            </SettingsCard>

            <SettingsCard icon={FiBell} title="Language coverage">
              <p className="text-sm leading-6 text-muted-foreground">
                Law Padi can return answers in English, Nigerian Pidgin, Yorùbá,
                Igbo and Hausa while keeping the official English text visible
                for verification.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                {["English", "Pidgin", "Yorùbá", "Igbo", "Hausa"].map(
                  (language) => (
                    <span
                      className="sq-sm border border-border bg-secondary px-3 py-2 text-xs font-semibold text-secondary-foreground"
                      key={language}
                    >
                      {language}
                    </span>
                  ),
                )}
              </div>
            </SettingsCard>
          </div>
        ) : null}

        {activeTab === "security" ? (
          <div className="grid gap-5 lg:grid-cols-2">
            <SettingsCard icon={FiLock} title="Privacy and data">
              <p className="text-sm leading-6 text-muted-foreground">
                Your questions are used to improve this local preview only.
                Saved provisions stay attached to your workspace and are never
                treated as legal advice.
              </p>
              <div className="mt-5 grid gap-3">
                <SquircleButton type="button" variant="outline">
                  <FiShield className="size-4" aria-hidden />
                  Export my research
                </SquircleButton>
                <SquircleButton type="button" variant="danger">
                  <FiLock className="size-4" aria-hidden />
                  Clear local activity
                </SquircleButton>
              </div>
            </SettingsCard>
            <SettingsCard icon={FiKey} title="Sign-in security">
              <div className="grid gap-3 text-sm">
                <div className="flex items-center gap-3 border-b border-border pb-4">
                  <div className="sq-sm grid size-9 place-items-center bg-accent text-accent-foreground">
                    <FiCheck className="size-4" aria-hidden />
                  </div>
                  <div>
                    <p className="font-semibold text-foreground">
                      Email verified
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Your account is ready for saved research.
                    </p>
                  </div>
                </div>
                <SquircleButton type="button" variant="outline">
                  <FiKey className="size-4" aria-hidden />
                  Change password
                </SquircleButton>
              </div>
            </SettingsCard>
          </div>
        ) : null}

        <div className="mt-6 flex flex-wrap items-center justify-end gap-3">
          {saved ? (
            <span className="inline-flex items-center gap-2 text-sm font-semibold text-primary">
              <FiCheck className="size-4" aria-hidden />
              Settings saved
            </span>
          ) : null}
          <SquircleButton
            onClick={() => setSaved(true)}
            type="button"
            variant="primary"
          >
            <FiSave className="size-4" aria-hidden />
            Save changes
          </SquircleButton>
        </div>
      </div>
    </section>
  )
}
