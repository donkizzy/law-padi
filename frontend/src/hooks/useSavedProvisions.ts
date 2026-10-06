import { useSyncExternalStore } from "react"
import { z } from "zod"

const storageKey = "law-padi.saved-provisions.v1"
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

const unreadable =
  "Saved bookmarks could not be read. Their browser data has been retained."
const unavailable =
  "Browser storage is unavailable. Saved provisions cannot be loaded."

function read() {
  let raw: string | null
  try {
    raw = localStorage.getItem(storageKey)
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
    if (event.key === storageKey || event.key === null) listener()
  }
  window.addEventListener("storage", storage)
  return () => {
    listeners.delete(listener)
    window.removeEventListener("storage", storage)
  }
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
    const next = saved
      ? existing.filter(
          (item) =>
            item.canonical_path !== path || item.release_version !== release,
        )
      : [
          ...existing,
          {
            canonical_path: path,
            release_version: release,
            saved_at: new Date().toISOString(),
          },
        ]
    // Only notify after durable browser storage succeeds.
    localStorage.setItem(storageKey, JSON.stringify(next))
    for (const listener of listeners) listener()
    return !saved
  }
  return { bookmarks, isSaved, toggle, storageError: error }
}
