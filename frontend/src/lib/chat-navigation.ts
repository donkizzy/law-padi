import { chatResetEvent } from "@/lib/storage-keys"

let focusAfterDrawer = false
export function requestComposerFocusAfterDrawer() {
  focusAfterDrawer = true
}
export function takeComposerFocusAfterDrawer() {
  const requested = focusAfterDrawer
  focusAfterDrawer = false
  return requested
}
export function cancelChatRequests() {
  window.dispatchEvent(new Event(chatResetEvent))
}
