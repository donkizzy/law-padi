export const chatResetEvent = "law-padi-new-conversation"
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
