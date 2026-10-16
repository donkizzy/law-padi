import { useSyncExternalStore } from "react"
import { z } from "zod"

export const workspaceStorageEvent = "law-padi-workspace-storage"
export const preferencesKey = "law-padi.preferences.v1"
export const draftPrefix = "law-padi.draft.v1."
const schema = z.object({
  enterToSend: z.boolean().default(true),
  followLatest: z.boolean().default(true),
  openSources: z.boolean().default(false),
})
export type WorkspacePreferences = z.infer<typeof schema>
export const defaultPreferences = schema.parse({})
let rawCache: string | null | undefined
let snapshot = { preferences: defaultPreferences, error: null as string | null }

function read() {
  try {
    const raw = localStorage.getItem(preferencesKey)
    if (raw === rawCache && !snapshot.error) return snapshot
    rawCache = raw
    const result = schema.safeParse(raw ? JSON.parse(raw) : {})
    snapshot = result.success
      ? { preferences: result.data, error: null }
      : {
          preferences: defaultPreferences,
          error:
            "Preferences could not be read. Your browser data has been retained.",
        }
  } catch {
    if (!snapshot.error)
      snapshot = {
        preferences: defaultPreferences,
        error: "Browser storage is unavailable. Preferences cannot be saved.",
      }
  }
  return snapshot
}

function subscribe(listener: () => void) {
  window.addEventListener("storage", listener)
  window.addEventListener(workspaceStorageEvent, listener)
  return () => {
    window.removeEventListener("storage", listener)
    window.removeEventListener(workspaceStorageEvent, listener)
  }
}

let changeListener: ((value: WorkspacePreferences) => void) | null = null

/** Account sync registers here to mirror saved preferences to the server. */
export function onPreferencesChange(listener: typeof changeListener) {
  changeListener = listener
}

export function readPreferences(): WorkspacePreferences {
  return read().preferences
}

function writePreferences(value: WorkspacePreferences) {
  localStorage.setItem(preferencesKey, JSON.stringify(schema.parse(value)))
  rawCache = undefined
  window.dispatchEvent(new Event(workspaceStorageEvent))
}

export function savePreferences(value: WorkspacePreferences) {
  writePreferences(value)
  changeListener?.(value)
}

/** Replace this browser's preferences with the account's, without echoing back. */
export const replacePreferences = writePreferences

export function clearPreferences() {
  localStorage.removeItem(preferencesKey)
  rawCache = undefined
  window.dispatchEvent(new Event(workspaceStorageEvent))
}

export function clearDrafts() {
  for (const key of Object.keys(sessionStorage))
    if (key.startsWith(draftPrefix)) sessionStorage.removeItem(key)
  window.dispatchEvent(new Event(workspaceStorageEvent))
}

export function useWorkspacePreferences() {
  return useSyncExternalStore(subscribe, read, read)
}
