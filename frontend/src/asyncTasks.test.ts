import { afterEach, describe, expect, it, vi } from 'vitest'
import { waitForPoll } from './asyncTasks'

describe('analysis poll lifecycle', () => {
  afterEach(() => vi.useRealTimers())
  it('removes the abort listener after a completed delay', async () => {
    vi.useFakeTimers()
    const controller = new AbortController()
    const remove = vi.spyOn(controller.signal, 'removeEventListener')
    const delay = waitForPoll(controller.signal)
    await vi.advanceTimersByTimeAsync(250)
    await delay
    expect(remove).toHaveBeenCalledWith('abort', expect.any(Function))
  })
  it('rejects immediately when cancelled before or during the delay', async () => {
    const controller = new AbortController()
    const waiting = waitForPoll(controller.signal)
    controller.abort()
    await expect(waiting).rejects.toMatchObject({ name: 'AbortError' })
    await expect(waitForPoll(controller.signal)).rejects.toMatchObject({ name: 'AbortError' })
  })
})
