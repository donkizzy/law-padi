import { toast } from "sonner"

import {
  AccountService,
  ConversationsService,
  type PreferencesBase,
  type UserPublic,
} from "@/client"
import { conversationHeaders } from "@/hooks/useConversations"
import {
  clearSavedProvisions,
  onBookmarkChange,
  readSavedProvisions,
  replaceSavedProvisions,
} from "@/hooks/useSavedProvisions"
import {
  clearPreferences,
  onPreferencesChange,
  readPreferences,
  replacePreferences,
  type WorkspacePreferences,
} from "@/hooks/useWorkspacePreferences"
import i18n from "@/lib/i18n"

/**
 * Keeps a confirmed account's research on every device it signs in on.
 *
 * The browser's bookmarks and preferences stay the copy the UI reads. The
 * first time an account syncs on a browser, what that browser saved as a guest
 * is merged into the account. From then on the browser mirrors the account:
 * it is refreshed from the server on load, each change is sent as it happens,
 * and signing out clears the mirrored copy.
 */

// Which account this browser's bookmarks and preferences currently mirror.
const SYNCED_ACCOUNT_KEY = "law-padi.synced-account"

let activeUserId: string | null = null
let starting: Promise<SyncResult> | null = null

export type SyncResult = { claimedConversations: number }

function storage<T>(action: (store: Storage) => T): T | undefined {
  try {
    return action(localStorage)
  } catch {
    return undefined
  }
}

const toServer = (value: WorkspacePreferences): PreferencesBase => ({
  enter_to_send: value.enterToSend,
  follow_latest: value.followLatest,
  open_sources: value.openSources,
})

// The account has no language field yet, so the language stays per browser.
const fromServer = (value: PreferencesBase): WorkspacePreferences => ({
  enterToSend: value.enter_to_send ?? true,
  followLatest: value.follow_latest ?? true,
  openSources: value.open_sources ?? false,
  language: readPreferences().language,
})

const syncFailed = () => toast.error(i18n.t("sync.updateFailed"))

onBookmarkChange(({ bookmark, saved }) => {
  if (!activeUserId) return
  const request = saved
    ? AccountService.saveProvision({ body: bookmark })
    : AccountService.removeSavedProvision({
        query: {
          canonical_path: bookmark.canonical_path,
          release_version: bookmark.release_version,
        },
      })
  request.catch(syncFailed)
})

onPreferencesChange((value) => {
  if (!activeUserId) return
  AccountService.savePreferences({ body: toServer(value) }).catch(syncFailed)
})

async function claimGuestConversations(): Promise<number> {
  try {
    const result = await ConversationsService.claimGuestConversations({
      headers: conversationHeaders(),
      withCredentials: true,
    })
    return result.data.claimed_count
  } catch {
    // Chat may be switched off, or there is nothing to claim.
    return 0
  }
}

async function sync(user: UserPublic): Promise<SyncResult> {
  const firstTime = storage((s) => s.getItem(SYNCED_ACCOUNT_KEY)) !== user.id

  const claimedConversations = await claimGuestConversations()

  const bookmarks = firstTime
    ? await AccountService.mergeSavedProvisions({
        body: { items: readSavedProvisions() },
      })
    : await AccountService.readSavedProvisions()
  replaceSavedProvisions(bookmarks.data)

  // The generated client turns a null body into {}, so check for a real value.
  const preferences = (await AccountService.readPreferences()).data
  if (typeof preferences?.enter_to_send === "boolean")
    replacePreferences(fromServer(preferences))
  else
    await AccountService.savePreferences({ body: toServer(readPreferences()) })

  storage((s) => s.setItem(SYNCED_ACCOUNT_KEY, user.id))
  activeUserId = user.id
  return { claimedConversations }
}

/** Start syncing for a confirmed account. Safe to call repeatedly. */
export function startAccountSync(user: UserPublic): Promise<SyncResult> {
  if (!user.email_verified_at || activeUserId === user.id)
    return Promise.resolve({ claimedConversations: 0 })
  starting ??= sync(user).finally(() => {
    starting = null
  })
  return starting
}

/** Stop syncing. On sign-out, drop the account's copy from this browser. */
export function stopAccountSync({ clearLocal }: { clearLocal: boolean }) {
  activeUserId = null
  if (!clearLocal) return
  if (storage((s) => s.getItem(SYNCED_ACCOUNT_KEY)) == null) return
  storage((s) => s.removeItem(SYNCED_ACCOUNT_KEY))
  try {
    clearSavedProvisions()
    clearPreferences()
  } catch {
    /* Signing out must work when browser storage is blocked. */
  }
}
