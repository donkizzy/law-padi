import { useCallback, useEffect, useState } from "react"
import { draftPrefix, workspaceStorageEvent } from "./useWorkspacePreferences"

export function useChatDraft(key: string) {
  const storageKey = `${draftPrefix}${key}`
  const [draft, updateDraft] = useState(() => {
    try {
      return sessionStorage.getItem(storageKey) ?? ""
    } catch {
      return ""
    }
  })
  const setDraft = useCallback(
    (value: string) => {
      try {
        if (value) sessionStorage.setItem(storageKey, value)
        else sessionStorage.removeItem(storageKey)
      } catch {
        /* Asking remains available when storage is blocked. */
      }
      updateDraft(value)
    },
    [storageKey],
  )
  useEffect(() => {
    const update = () => {
      try {
        setDraft(sessionStorage.getItem(storageKey) ?? "")
      } catch {
        /* Keep the editable draft. */
      }
    }
    window.addEventListener(workspaceStorageEvent, update)
    return () => window.removeEventListener(workspaceStorageEvent, update)
  }, [storageKey, setDraft])
  return [draft, setDraft] as const
}
