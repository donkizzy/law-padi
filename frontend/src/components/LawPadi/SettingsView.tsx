import { Link } from "@tanstack/react-router"
import { type ReactNode, useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { FiLock, FiSettings, FiUser } from "react-icons/fi"
import { toast } from "sonner"
import { LanguageChoice } from "@/components/Common/LanguagePicker"
import { AccountData } from "@/components/UserSettings/AccountData"
import ChangePassword from "@/components/UserSettings/ChangePassword"
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
  const { t } = useTranslation(["settings", "common"])
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
      // The language applies as soon as it is picked, so keep the saved one.
      savePreferences({ ...edited, language: preferences.language })
      setDirty(false)
      setSaved(true)
      setError(null)
    } catch {
      setError(t("errors.saveFailed"))
      setSaved(false)
    }
  }
  return (
    <section className="mx-auto max-w-5xl px-4 py-8 sm:px-8 lg:px-12">
      <SectionHeading kicker={t("kicker")} title={t("title")}>
        {t("intro")}
      </SectionHeading>
      <Tabs defaultValue="profile">
        <TabsList
          className="sq-md mb-5 h-12 max-w-full justify-start overflow-x-auto"
          aria-label={t("tabs.label")}
        >
          <TabsTrigger className="sq-sm px-4" value="profile">
            <FiUser aria-hidden />
            {t("tabs.profile")}
          </TabsTrigger>
          <TabsTrigger className="sq-sm px-4" value="preferences">
            <FiSettings aria-hidden />
            {t("tabs.preferences")}
          </TabsTrigger>
          <TabsTrigger className="sq-sm px-4" value="security">
            <FiLock aria-hidden />
            {t("tabs.security")}
          </TabsTrigger>
        </TabsList>
        <TabsContent
          value="profile"
          className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]"
        >
          <SettingsCard title={t("tabs.profile")}>
            {user ? (
              <>
                <EmailVerificationNotice />
                <UserInformation />
              </>
            ) : isLoggedIn() ? (
              <p role="status">{t("guest.loading")}</p>
            ) : (
              <div className="grid gap-4">
                <p className="text-body">{t("guest.body")}</p>
                <p className="text-sm text-muted-foreground">
                  {t("guest.signInBenefit")}
                </p>
                <div className="flex flex-wrap gap-2">
                  <SquircleButton asChild>
                    <Link to="/login" search={{ redirect: "/settings" }}>
                      {t("common:auth.signIn")}
                    </Link>
                  </SquircleButton>
                  <SquircleButton asChild variant="outline">
                    <Link to="/signup" search={{ redirect: "/settings" }}>
                      {t("common:auth.createAccount")}
                    </Link>
                  </SquircleButton>
                </div>
              </div>
            )}
          </SettingsCard>
          <SettingsCard title={t("available.title")}>
            <dl className="grid gap-3 text-body">
              <dt className="text-muted-foreground">
                {t("available.account")}
              </dt>
              <dd>{user ? t("available.signedIn") : t("available.guest")}</dd>
              <dt className="text-muted-foreground">
                {t("available.edition")}
              </dt>
              <dd>
                {release.data
                  ? editionName(release.data.edition_label)
                  : t("available.editionUnavailable")}
              </dd>
              <dt className="text-muted-foreground">
                {t("available.explanations")}
              </dt>
              <dd>
                {capabilities.isError
                  ? t("available.unknown")
                  : capabilities.data?.explanations_enabled
                    ? t("available.on")
                    : t("available.paused")}
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
                {t("common:actions.checkAgain")}
              </InlineAction>
            )}
          </SettingsCard>
        </TabsContent>
        <TabsContent
          value="preferences"
          className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]"
        >
          <SettingsCard title={t("reading.title")}>
            <SettingToggle
              label={t("reading.enterToSend")}
              description={t("reading.enterToSendHint")}
              value={edited.enterToSend}
              onChange={() => update("enterToSend")}
            />
            <SettingToggle
              label={t("reading.followLatest")}
              description={t("reading.followLatestHint")}
              value={edited.followLatest}
              onChange={() => update("followLatest")}
            />
            <SettingToggle
              label={t("reading.openSources")}
              description={t("reading.openSourcesHint")}
              value={edited.openSources}
              onChange={() => update("openSources")}
            />
            <p className="mt-3 text-sm text-muted-foreground">
              {user?.email_verified_at
                ? t("reading.syncedToAccount")
                : t("reading.savedOnBrowser")}
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <SquircleButton type="button" disabled={!dirty} onClick={save}>
                {t("reading.save")}
              </SquircleButton>
              {saved && (
                <span role="status" className="text-sm text-primary">
                  {t("reading.saved")}
                </span>
              )}
            </div>
          </SettingsCard>
          <SettingsCard title={t("language.title")}>
            <LanguageChoice />
            <p className="mt-4 text-sm text-muted-foreground">
              {t("language.official")}
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              {t("language.savedOnBrowser")}
            </p>
          </SettingsCard>
        </TabsContent>
        <TabsContent value="security" className="grid gap-5">
          <SettingsCard title={t("privacy.title")}>
            <div className="grid gap-3 text-body text-muted-foreground">
              <p>
                {user?.email_verified_at
                  ? t("privacy.keptInAccount")
                  : t("privacy.keptOnBrowser")}{" "}
                {t("privacy.retention")}
              </p>
              <p>{t("privacy.provider")}</p>
              <p>{t("privacy.exportFirst")}</p>
              <p>
                <Link
                  className="font-semibold text-primary underline"
                  to="/privacy"
                >
                  {t("privacy.readMore")}
                </Link>
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
                      throw new Error("Chat availability unknown")
                    await exportResearch(
                      capabilities.data?.conversations_enabled === true,
                    )
                    toast.success(t("privacy.exported"))
                  } catch {
                    setError(t("errors.exportFailed"))
                  } finally {
                    setExporting(false)
                  }
                }}
              >
                {t("privacy.export")}
              </SquircleButton>
              <SquircleButton
                type="button"
                variant="danger"
                onClick={() => setClearOpen(true)}
              >
                {t("privacy.clear")}
              </SquircleButton>
            </div>
          </SettingsCard>
          {user && (
            <SettingsCard title={t("security.title")}>
              <ChangePassword />
            </SettingsCard>
          )}
          {user && (
            <SettingsCard title={t("data.title")}>
              <AccountData />
            </SettingsCard>
          )}
          {user?.is_superuser && (
            <SettingsCard title={t("qualitySignals")}>
              <ChatMetricsView />
            </SettingsCard>
          )}
          <details className="sq-md border border-border p-4">
            <summary className="cursor-pointer text-body font-semibold">
              {t("support.title")}
            </summary>
            <dl className="mt-3 grid gap-2 text-sm">
              <dt>{t("support.appBuild")}</dt>
              <dd className="break-all">
                {import.meta.env.VITE_BUILD_REVISION ?? "development"}
              </dd>
              <dt>{t("support.serviceBuild")}</dt>
              <dd className="break-all">
                {capabilities.data?.build_revision ?? t("support.unavailable")}
              </dd>
              <dt>{t("support.sourceRelease")}</dt>
              <dd className="break-all">
                {release.data?.release_version ?? t("support.unavailable")}
              </dd>
            </dl>
          </details>
        </TabsContent>
      </Tabs>
      {(error || storageError) && (
        <p className="mt-5 sq-md bg-destructive/10 p-4 text-body" role="alert">
          {error || (storageError && t(`common:${storageError}` as never))}
        </p>
      )}
      <Dialog open={clearOpen} onOpenChange={setClearOpen}>
        <DialogContent className="sq-lg">
          <DialogTitle>{t("clear.title")}</DialogTitle>
          <DialogDescription>{t("clear.body")}</DialogDescription>
          <DialogFooter>
            <DialogClose asChild>
              <SquircleButton variant="outline" type="button">
                {t("clear.keep")}
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
                  toast.success(t("clear.done"))
                } catch {
                  setError(t("errors.clearFailed"))
                }
              }}
            >
              {t("clear.confirm")}
            </SquircleButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
