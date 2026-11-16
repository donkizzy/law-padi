/// <reference lib="es2021.weakref" />

/** A reference that may stop pointing at anything once its target is collected. */
type Weak<T extends object> = { deref(): T | undefined }

const weak = <T extends object>(value: T): Weak<T> =>
  typeof WeakRef === "function" ? new WeakRef(value) : { deref: () => value }

/** The signals following one source, and how large the set may grow before a sweep. */
type Followers = { refs: Set<Weak<AbortSignal>>; sweepAt: number }

const MIN_SWEEP = 64

/** The controller behind a linked signal, kept alive exactly as long as the signal. */
const controllers = new WeakMap<AbortSignal, AbortController>()

const followers = new WeakMap<AbortSignal, Followers>()

/**
 * Makes `linked` abort when `source` does.
 *
 * A source gets one `abort` listener however many signals follow it. That
 * matters for the session signal, which outlives every request: a listener
 * per request would pile up on it, because a request that succeeds never
 * aborts its own signal and so never gets to remove the listener. Followers
 * are held weakly instead, so a finished request that has been collected
 * leaves only a dead entry, and dead or aborted entries are swept whenever
 * the set doubles, which keeps the cost per request constant.
 */
function follow(source: AbortSignal, linked: AbortSignal) {
  let entry = followers.get(source)
  if (!entry) {
    const created: Followers = { refs: new Set(), sweepAt: MIN_SWEEP }
    entry = created
    followers.set(source, created)
    source.addEventListener(
      "abort",
      () => {
        for (const ref of created.refs) {
          const signal = ref.deref()
          if (signal && !signal.aborted)
            controllers.get(signal)?.abort(source.reason)
        }
        created.refs.clear()
      },
      { once: true },
    )
  }
  entry.refs.add(weak(linked))
  if (entry.refs.size >= entry.sweepAt) {
    for (const ref of entry.refs) {
      const signal = ref.deref()
      if (!signal || signal.aborted) entry.refs.delete(ref)
    }
    entry.sweepAt = Math.max(MIN_SWEEP, entry.refs.size * 2)
  }
}

/**
 * A signal that aborts when any of `signals` does, carrying that signal's
 * reason. Uses `AbortSignal.any` where the browser has it (Chrome 116,
 * Safari 17.4, Firefox 124) and links the signals by hand elsewhere.
 */
export function anySignal(signals: readonly AbortSignal[]): AbortSignal {
  if (typeof AbortSignal.any === "function")
    return AbortSignal.any([...signals])

  const controller = new AbortController()
  const aborted = signals.find((signal) => signal.aborted)
  if (aborted) {
    controller.abort(aborted.reason)
    return controller.signal
  }
  controllers.set(controller.signal, controller)
  for (const signal of signals) follow(signal, controller.signal)
  return controller.signal
}
