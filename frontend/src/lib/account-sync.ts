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
  readGuestBookmarks,
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
import {
  getSessionOwner,
  getSessionScope,
  getSessionSignal,
} from "@/lib/session"
import { syncedAccountKey } from "@/lib/storage-keys"

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
const SYNCED_ACCOUNT_KEY = syncedAccountKey

let activeUserId: string | null = null
let starting: { scope: number; promise: Promise<SyncResult> } | null = null

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
  language: value.language,
})

// An account that has never saved a language keeps this browser's choice.
const fromServer = (value: PreferencesBase): WorkspacePreferences => ({
  enterToSend: value.enter_to_send ?? true,
  followLatest: value.follow_latest ?? true,
  openSources: value.open_sources ?? false,
  language:
    (value.language as WorkspacePreferences["language"] | null | undefined) ??
    readPreferences().language,
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
  const scope = getSessionScope()
  const signal = getSessionSignal()
  const ownerKey = `${SYNCED_ACCOUNT_KEY}.${user.id}`
  const firstTime = storage((s) => s.getItem(ownerKey)) !== "1"
  const guestBookmarks = firstTime ? readGuestBookmarks() : []
  const localBookmarks = firstTime ? readSavedProvisions() : []

  const claimedConversations = await claimGuestConversations()
  signal.throwIfAborted()

  const bookmarks = firstTime
    ? await AccountService.mergeSavedProvisions({
        body: { items: [...guestBookmarks, ...localBookmarks] },
        signal,
      })
    : await AccountService.readSavedProvisions({ signal })
  signal.throwIfAborted()
  if (
    guestBookmarks.length &&
    JSON.stringify(guestBookmarks) === JSON.stringify(readGuestBookmarks())
  )
    clearSavedProvisions(null)
  replaceSavedProvisions(bookmarks.data)

  // The generated client turns a null body into {}, so check for a real value.
  const preferences = (await AccountService.readPreferences({ signal })).data
  signal.throwIfAborted()
  if (typeof preferences?.enter_to_send === "boolean") {
    replacePreferences(fromServer(preferences))
    // Older saves have no language: store this browser's choice.
    if (!preferences.language)
      await AccountService.savePreferences({
        body: toServer(readPreferences()),
        signal,
      })
  } else
    await AccountService.savePreferences({
      body: toServer(readPreferences()),
      signal,
    })

  if (scope !== getSessionScope()) return { claimedConversations: 0 }
  storage((s) => s.setItem(ownerKey, "1"))
  activeUserId = user.id
  return { claimedConversations }
}

/** Start syncing for a confirmed account. Safe to call repeatedly. */
export function startAccountSync(user: UserPublic): Promise<SyncResult> {
  const owner = getSessionOwner()
  if (
    !owner ||
    (owner !== "signed-in" && owner !== user.id) ||
    !user.email_verified_at ||
    activeUserId === user.id
  )
    return Promise.resolve({ claimedConversations: 0 })
  const scope = getSessionScope()
  if (starting?.scope === scope) return starting.promise
  const promise = sync(user).finally(() => {
    if (starting?.promise === promise) starting = null
  })
  starting = { scope, promise }
  return promise
}

/** Stop syncing. On sign-out, drop the account's copy from this browser. */
export function stopAccountSync(previousOwner: string | null) {
  activeUserId = null
  if (!previousOwner) return
  try {
    clearSavedProvisions(previousOwner)
    clearPreferences()
  } catch {
    /* Signing out must work when browser storage is blocked. */
  }
}
