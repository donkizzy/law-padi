// Names of what this browser keeps for the reader, and the move from the names
// the product used before it became constitution.ng.

/** localStorage: interface preferences (language, Enter to send, …). */
export const preferencesKey = "constitution-ng.preferences.v1"
/** sessionStorage prefix: unsent questions, per account and conversation. */
export const draftPrefix = "constitution-ng.draft.v2."
/** localStorage prefix: saved provisions; the guest's under the bare key, an account's under `.<id>`. */
export const savedProvisionsKey = "constitution-ng.saved-provisions.v2"
/** localStorage: which account this browser's research mirrors, and per-account markers under `.<id>`. */
export const syncedAccountKey = "constitution-ng.synced-account"
/** localStorage: light, dark or system theme. */
export const themeKey = "constitution-ng.theme"

// Window events that keep same-page stores and requests in step.
export const workspaceStorageEvent = "constitution-ng:workspace-storage"
export const chatResetEvent = "constitution-ng:new-conversation"

// Each earlier name, matched as a prefix so per-account and per-conversation
// keys move with their family. Older formats that their own migrations read
// (`saved-provisions.v1`, `draft.v1.`) keep their names until those discard them.
const renamed: ReadonlyArray<{
  store: () => Storage
  from: string
  to: string
}> = [
  {
    store: () => localStorage,
    from: "law-padi.preferences.v1",
    to: preferencesKey,
  },
  {
    store: () => localStorage,
    from: "law-padi.saved-provisions.v2",
    to: savedProvisionsKey,
  },
  {
    store: () => localStorage,
    from: "law-padi.synced-account",
    to: syncedAccountKey,
  },
  { store: () => localStorage, from: "law-padi-theme", to: themeKey },
  { store: () => sessionStorage, from: "law-padi.draft.v2.", to: draftPrefix },
]

/**
 * Moves anything stored under an earlier name to its current one and deletes
 * the old entry. A value already under the current name is kept. Blocked or
 * full storage leaves things as they are; the stores report that themselves.
 */
export function migrateStorageKeys() {
  for (const { store, from, to } of renamed) {
    try {
      const storage = store()
      for (const key of Object.keys(storage)) {
        if (!key.startsWith(from)) continue
        const next = `${to}${key.slice(from.length)}`
        const value = storage.getItem(key)
        if (value !== null && storage.getItem(next) === null)
          storage.setItem(next, value)
        storage.removeItem(key)
      }
    } catch {
      // Storage unavailable: nothing to move.
    }
  }
}

// Every module that reads these keys imports them from here, so the move runs
// before the first read, including the language read while i18n starts.
migrateStorageKeys()
