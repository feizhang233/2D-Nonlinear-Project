/** One abort listener per delay; completed polls must not accumulate listeners. */
export function waitForPoll(signal: AbortSignal, milliseconds = 250): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException('Polling aborted', 'AbortError')); return }
    const abort = () => {
      clearTimeout(timeout)
      reject(new DOMException('Polling aborted', 'AbortError'))
    }
    const timeout = setTimeout(() => {
      signal.removeEventListener('abort', abort)
      resolve()
    }, milliseconds)
    signal.addEventListener('abort', abort, { once: true })
  })
}
