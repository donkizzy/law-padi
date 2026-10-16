import { useCallback, useEffect, useRef } from "react"
import { chatResetEvent } from "@/lib/chat-navigation"

/** A response belongs only to the mounted conversation that requested it. */
export function useChatRequestScope() {
  const mounted = useRef(false)
  const controllers = useRef(new Set<AbortController>())
  useEffect(() => {
    mounted.current = true
    const abandon = () => {
      mounted.current = false
      for (const controller of controllers.current) controller.abort()
      controllers.current.clear()
    }
    window.addEventListener(chatResetEvent, abandon)
    return () => {
      window.removeEventListener(chatResetEvent, abandon)
      abandon()
    }
  }, [])
  return useCallback(() => {
    const controller = new AbortController()
    controllers.current.add(controller)
    return {
      signal: controller.signal,
      current: () => mounted.current && !controller.signal.aborted,
      close: () => {
        controller.abort()
        controllers.current.delete(controller)
      },
    }
  }, [])
}
