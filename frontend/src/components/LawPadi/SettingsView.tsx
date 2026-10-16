import { Link } from "@tanstack/react-router"
import { type ReactNode, useEffect, useState } from "react"
import { FiGlobe, FiLock, FiSettings, FiUser } from "react-icons/fi"
import { toast } from "sonner"
import ChangePassword from "@/components/UserSettings/ChangePassword"
import DeleteAccount from "@/components/UserSettings/DeleteAccount"
import { EmailVerificationNotice } from "@/components/UserSettings/EmailVerificationNotice"
import UserInformation from "@/components/UserSettings/UserInformation"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"
import { useChatCapabilities } from "@/hooks/useChatCapabilities"
import { useLegalRelease } from "@/hooks/useLegalCorpus"
import { clearSavedProvisions } from "@/hooks/useSavedProvisions"
import {
  clearDrafts,
  savePreferences,
  useWorkspacePreferences,
  type WorkspacePreferences,
} from "@/hooks/useWorkspacePreferences"
import { editionName } from "@/lib/legal-provisions"
import { exportResearch } from "@/lib/research"
import { ChatMetricsView } from "./ChatMetricsView"
import { EditionNotice } from "./EditionNotice"
import { InlineAction, SectionHeading, SquircleButton } from "./primitives"

function SettingsCard({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <section className="sq-lg border border-border bg-card p-5 sm:p-6">
      <h2 className="mb-4 font-display text-title-3">{title}</h2>
      {children}
    </section>
  )
}

function SettingToggle({
  label,
  description,
  value,
  onChange,
}: {
  label: string
  description: string
  value: boolean
  onChange: () => void
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-t border-border py-4 first:border-t-0">
      <div>
        <p className="text-body font-semibold">{label}</p>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      <button
        className="sq-sm grid min-h-11 min-w-14 place-items-center focus-visible:ring-2 focus-visible:ring-ring"
        type="button"
        role="switch"
        aria-checked={value}
        aria-label={label}
        onClick={onChange}
      >
        <span
          aria-hidden
          className={`sq-sm flex h-7 w-12 items-center p-1 ${value ? "justify-end bg-primary" : "justify-start bg-secondary"}`}
        >
          <span
            className={`sq-xs size-5 ${value ? "bg-primary-foreground" : "bg-muted-foreground"}`}
          />
        </span>
      </button>
    </div>
  )
}

export function SettingsView() {
  const { user } = useAuth()
  const capabilities = useChatCapabilities()
  const release = useLegalRelease()
  const { preferences, error: storageError } = useWorkspacePreferences()
  const [edited, setEdited] = useState(preferences)
  const [dirty, setDirty] = useState(false)
  const [saved, setSaved] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [clearOpen, setClearOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (!dirty) setEdited(preferences)
  }, [dirty, preferences])
  const update = (key: keyof WorkspacePreferences) => {
    setEdited((value) => ({ ...value, [key]: !value[key] }))
    setDirty(true)
    setSaved(false)
  }
  const save = () => {
    try {
      savePreferences(edited)
      setDirty(false)
      setSaved(true)
      setError(null)
    } catch {
      setError(
        "Your browser couldn't save these preferences. Please try again.",
      )
      setSaved(false)
    }
  }
  return (
    <section className="mx-auto max-w-5xl px-4 py-8 sm:px-8 lg:px-12">
      <SectionHeading kicker="Settings" title="Make constitution.ng yours.">
        Manage your account, reading preferences and saved research.
      </SectionHeading>
      <Tabs defaultValue="profile">
        <TabsList
          className="sq-md mb-5 h-12 max-w-full"
          aria-label="Settings sections"
        >
          <TabsTrigger className="sq-sm px-4" value="profile">
            <FiUser aria-hidden />
            Profile
          </TabsTrigger>
          <TabsTrigger className="sq-sm px-4" value="preferences">
            <FiSettings aria-hidden />
            Preferences
          </TabsTrigger>
          <TabsTrigger className="sq-sm px-4" value="security">
            <FiLock aria-hidden />
            Security
          </TabsTrigger>
        </TabsList>
        <TabsContent
          value="profile"
          className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]"
        >
          <SettingsCard title="Profile">
            {user ? (
              <>
                <EmailVerificationNotice />
                <UserInformation />
              </>
            ) : isLoggedIn() ? (
              <p role="status">Loading your account…</p>
            ) : (
              <div className="grid gap-4">
                <p className="text-body">
                  You're browsing as a guest. You can ask questions and save
                  sections without an account.
                </p>
                <p className="text-sm text-muted-foreground">
                  Sign in to keep your conversations and saved sections on every
                  device. Anything you've saved here comes with you.
                </p>
                <div className="flex flex-wrap gap-2">
                  <SquircleButton asChild>
                    <Link to="/login" search={{ redirect: "/settings" }}>
                      Sign in
                    </Link>
                  </SquircleButton>
                  <SquircleButton asChild variant="outline">
                    <Link to="/signup" search={{ redirect: "/settings" }}>
                      Create account
                    </Link>
                  </SquircleButton>
                </div>
              </div>
            )}
          </SettingsCard>
          <SettingsCard title="Available here">
            <dl className="grid gap-3 text-body">
              <dt className="text-muted-foreground">Account</dt>
              <dd>{user ? "Signed in" : "Guest"}</dd>
              <dt className="text-muted-foreground">Source edition</dt>
              <dd>
                {release.data
                  ? editionName(release.data.edition_label)
                  : "Edition unavailable"}
              </dd>
              <dt className="text-muted-foreground">Answer language</dt>
              <dd>English</dd>
              <dt className="text-muted-foreground">Explanations</dt>
              <dd>
                {capabilities.isError
                  ? "Availability unknown"
                  : capabilities.data?.explanations_enabled
                    ? "Available"
                    : "Paused"}
              </dd>
            </dl>
            <EditionNotice
              className="mt-5"
              label={release.data?.edition_label}
              historical={release.data?.legal_statuses.includes("historical")}
            />
            {(release.isError || capabilities.isError) && (
              <InlineAction
                className="mt-3"
                type="button"
                onClick={() => {
                  void release.refetch()
                  void capabilities.refetch()
                }}
              >
                Check again
              </InlineAction>
            )}
          </SettingsCard>
        </TabsContent>
        <TabsContent
          value="preferences"
          className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]"
        >
          <SettingsCard title="Reading and asking">
            <SettingToggle
              label="Enter to send"
              description="Use Shift+Enter for a new line. Ctrl/Cmd+Enter always sends."
              value={edited.enterToSend}
              onChange={() => update("enterToSend")}
            />
            <SettingToggle
              label="Follow latest answer"
              description="Scroll to new messages while you're near the end of the chat."
              value={edited.followLatest}
              onChange={() => update("followLatest")}
            />
            <SettingToggle
              label="Open source beside answers"
              description="On desktop, open the first linked source after an explanation finishes."
              value={edited.openSources}
              onChange={() => update("openSources")}
            />
            <p className="mt-3 text-sm text-muted-foreground">
              {user?.email_verified_at
                ? "These preferences follow your account to any device."
                : "These preferences are saved on this browser."}
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <SquircleButton type="button" disabled={!dirty} onClick={save}>
                Save changes
              </SquircleButton>
              {saved && (
                <span role="status" className="text-sm text-primary">
                  Settings saved
                </span>
              )}
            </div>
          </SettingsCard>
          <SettingsCard title="Answer language">
            <FiGlobe className="mb-3 size-5 text-primary" aria-hidden />
            <p className="text-body">
              Answers are currently available in English.
            </p>
            <p className="mt-3 text-sm text-muted-foreground">
              Official constitutional wording stays in English. Other answer
              languages and amendment notifications aren't available yet.
            </p>
          </SettingsCard>
        </TabsContent>
        <TabsContent value="security" className="grid gap-5">
          <SettingsCard title="Privacy and research">
            <div className="grid gap-3 text-body text-muted-foreground">
              <p>
                Bookmarks stay on this browser. Drafts stay in this tab until it
                closes. Conversations are stored by the service and attached to
                your account or guest browser session.
              </p>
              <p>
                When explanations are enabled, your question and relevant
                constitutional text are sent to DeepSeek to write and check the
                answer. Avoid including personal details you don't need to
                share.
              </p>
              <p>
                Export your bookmarks, preferences and available conversations
                before clearing local research. Source editions and citations
                are kept in the export.
              </p>
            </div>
            <div className="mt-5 flex flex-wrap gap-3">
              <SquircleButton
                type="button"
                variant="outline"
                loading={exporting}
                onClick={async () => {
                  setExporting(true)
                  setError(null)
                  try {
                    if (capabilities.isError)
                      throw new Error("Availability unknown")
                    await exportResearch(
                      capabilities.data?.conversations_enabled === true,
                    )
                    toast.success("Research exported")
                  } catch {
                    setError(
                      "Your research could not be fully exported. Check your connection and try again.",
                    )
                  } finally {
                    setExporting(false)
                  }
                }}
              >
                Export my research
              </SquircleButton>
              <SquircleButton
                type="button"
                variant="danger"
                onClick={() => setClearOpen(true)}
              >
                Clear bookmarks and drafts
              </SquircleButton>
            </div>
          </SettingsCard>
          {user && (
            <SettingsCard title="Sign-in security">
              <ChangePassword />
              <DeleteAccount />
            </SettingsCard>
          )}
          {user?.is_superuser && (
            <SettingsCard title="Answer quality signals">
              <ChatMetricsView />
            </SettingsCard>
          )}
          <details className="sq-md border border-border p-4">
            <summary className="cursor-pointer text-body font-semibold">
              Support details
            </summary>
            <dl className="mt-3 grid gap-2 text-sm">
              <dt>App build</dt>
              <dd className="break-all">
                {import.meta.env.VITE_BUILD_REVISION ?? "development"}
              </dd>
              <dt>Service build</dt>
              <dd className="break-all">
                {capabilities.data?.build_revision ?? "Unavailable"}
              </dd>
              <dt>Source release</dt>
              <dd className="break-all">
                {release.data?.release_version ?? "Unavailable"}
              </dd>
            </dl>
          </details>
        </TabsContent>
      </Tabs>
      {(error || storageError) && (
        <p className="mt-5 sq-md bg-destructive/10 p-4 text-body" role="alert">
          {error || storageError}
        </p>
      )}
      <Dialog open={clearOpen} onOpenChange={setClearOpen}>
        <DialogContent className="sq-lg">
          <DialogTitle>Clear local bookmarks and drafts?</DialogTitle>
          <DialogDescription>
            This removes your bookmarks from this browser and drafts from this
            tab. Your account and saved conversations stay available. Export
            your research first if you want a copy.
          </DialogDescription>
          <DialogFooter>
            <DialogClose asChild>
              <SquircleButton variant="outline" type="button">
                Keep my research
              </SquircleButton>
            </DialogClose>
            <SquircleButton
              variant="danger"
              type="button"
              onClick={() => {
                try {
                  clearSavedProvisions()
                  clearDrafts()
                  setClearOpen(false)
                  toast.success("Local bookmarks and drafts cleared")
                } catch {
                  setError(
                    "Some local research could not be cleared. Please check your browser storage.",
                  )
                }
              }}
            >
              Clear local research
            </SquircleButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
