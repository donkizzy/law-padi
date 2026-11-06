import { useSyncExternalStore } from "react"
import { z } from "zod"
import { getSessionOwner } from "@/lib/session"

const storageKey = "law-padi.saved-provisions.v2"
const legacyStorageKey = "law-padi.saved-provisions.v1"
const legacyOwnerKey = "law-padi.synced-account"
const migratedKey = `${storageKey}.migrated`
const keyFor = (owner: string | null) =>
  owner ? `${storageKey}.${owner}` : storageKey
const bookmarkSchema = z.array(
  z.object({
    canonical_path: z.string().min(1),
    release_version: z.string().min(1),
    saved_at: z.string(),
  }),
)
export type Bookmark = z.infer<typeof bookmarkSchema>[number]
const empty: Bookmark[] = []
const initialSnapshot = { bookmarks: empty, error: null as string | null }
let cachedRaw: string | null | undefined
let cached = initialSnapshot
const listeners = new Set<() => void>()

// Errors are `common` catalogue keys so the message follows the language.
const unreadable = "saved.unreadable"
const unavailable = "saved.storageUnavailable"

function read() {
  let raw: string | null
  try {
    raw = localStorage.getItem(keyFor(getSessionOwner()))
  } catch {
    if (cached.error !== unavailable)
      cached = { bookmarks: empty, error: unavailable }
    return cached
  }
  if (raw === cachedRaw && cached.error !== unavailable) return cached
  cachedRaw = raw
  try {
    const result = bookmarkSchema.safeParse(raw ? JSON.parse(raw) : [])
    cached = {
      bookmarks: result.success ? result.data : empty,
      error: result.success ? null : unreadable,
    }
  } catch {
    cached = { bookmarks: empty, error: unreadable }
  }
  return cached
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  const storage = (event: StorageEvent) => {
    if (event.key === keyFor(getSessionOwner()) || event.key === null)
      listener()
  }
  window.addEventListener("storage", storage)
  return () => {
    listeners.delete(listener)
    window.removeEventListener("storage", storage)
  }
}

export type BookmarkChange = { bookmark: Bookmark; saved: boolean }
let changeListener: ((change: BookmarkChange) => void) | null = null

/** Account sync registers here to mirror each local change to the server. */
export function onBookmarkChange(listener: typeof changeListener) {
  changeListener = listener
}

export function readSavedProvisions(): Bookmark[] {
  return read().bookmarks
}

export function readGuestBookmarks(): Bookmark[] {
  try {
    return bookmarkSchema.parse(
      JSON.parse(localStorage.getItem(storageKey) ?? "[]"),
    )
  } catch {
    return []
  }
}

/** Only move legacy data that was stored in a guest browser. */
export function migrateLegacyBookmarks(hadAccountSession: boolean) {
  if (localStorage.getItem(migratedKey)) return
  const legacy = localStorage.getItem(legacyStorageKey)
  if (
    legacy !== null &&
    !hadAccountSession &&
    !localStorage.getItem(legacyOwnerKey) &&
    localStorage.getItem(storageKey) === null
  )
    localStorage.setItem(storageKey, legacy)
  localStorage.setItem(migratedKey, "1")
  localStorage.removeItem(legacyStorageKey)
  localStorage.removeItem(legacyOwnerKey)
}

/** Replace this browser's bookmarks with the account's, without echoing back. */
export function replaceSavedProvisions(next: Bookmark[]) {
  localStorage.setItem(
    keyFor(getSessionOwner()),
    JSON.stringify(bookmarkSchema.parse(next)),
  )
  for (const listener of listeners) listener()
}

export function clearSavedProvisions(owner = getSessionOwner()) {
  localStorage.removeItem(keyFor(owner))
  cachedRaw = undefined
  for (const listener of listeners) listener()
}

export function useSavedProvisions() {
  const { bookmarks, error } = useSyncExternalStore(
    subscribe,
    read,
    () => initialSnapshot,
  )
  const isSaved = (path: string, release: string) =>
    bookmarks.some(
      (item) =>
        item.canonical_path === path && item.release_version === release,
    )
  const toggle = (path: string, release: string) => {
    const snapshot = read()
    if (snapshot.error) throw new Error(snapshot.error)
    const existing = snapshot.bookmarks
    const saved = existing.some(
      (item) =>
        item.canonical_path === path && item.release_version === release,
    )
    const bookmark = {
      canonical_path: path,
      release_version: release,
      saved_at: new Date().toISOString(),
    }
    const next = saved
      ? existing.filter(
          (item) =>
            item.canonical_path !== path || item.release_version !== release,
        )
      : [...existing, bookmark]
    // Only notify after durable browser storage succeeds.
    localStorage.setItem(keyFor(getSessionOwner()), JSON.stringify(next))
    for (const listener of listeners) listener()
    changeListener?.({ bookmark, saved: !saved })
    return !saved
  }
  return { bookmarks, isSaved, toggle, storageError: error }
}
