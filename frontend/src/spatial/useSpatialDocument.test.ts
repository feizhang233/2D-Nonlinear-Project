// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useSpatialDocument } from './useSpatialDocument'

type Model = { name: string }
const parse = (value: unknown): Model => {
  if (!value || typeof (value as Model).name !== 'string') throw new Error('Invalid model')
  return structuredClone(value as Model)
}
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: Error) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const file = (read: () => Promise<string>) => ({ size: 10, text: read }) as File
beforeEach(() => {
  Object.defineProperty(window, 'localStorage', { configurable: true, value: {
    getItem: vi.fn(() => null), setItem: vi.fn(),
  } })
})
afterEach(() => cleanup())
function mount(solve = vi.fn(async () => 'result'), validate = vi.fn(async (m: Model) => m)) {
  return renderHook(({ active }) => useSpatialDocument({ storage: 'test', active,
    example: () => ({ name: 'original' }), parse, solve, validate,
  }), { initialProps: { active: true } })
}

it('blocks duplicate solves and ignores a late response after editing', async () => {
  const pending = deferred<string>()
  const solve = vi.fn(() => pending.promise)
  const hook = mount(solve)
  let running!: Promise<unknown>
  act(() => { running = hook.result.current.run(); void hook.result.current.run() })
  expect(solve).toHaveBeenCalledTimes(1)
  act(() => { hook.result.current.change({ name: 'edited' }, 'Changed') })
  await act(async () => { pending.resolve('stale result'); await running })
  expect(hook.result.current.result).toBeNull()
  expect(hook.result.current.model.name).toBe('edited')
  act(() => { hook.result.current.undo() })
  expect(hook.result.current.model.name).toBe('original')
  act(() => { hook.result.current.redo() })
  expect(hook.result.current.model.name).toBe('edited')
})

it('cancels file reading on navigation before sending validation', async () => {
  const reading = deferred<string>()
  const validate = vi.fn(async (m: Model) => m)
  const hook = mount(undefined, validate)
  let importing!: Promise<unknown>
  act(() => { importing = hook.result.current.importFile(file(() => reading.promise)) })
  hook.rerender({ active: false })
  await act(async () => { reading.resolve('{"name":"late"}'); await importing })
  expect(validate).not.toHaveBeenCalled()
  expect(hook.result.current.model.name).toBe('original')
  expect(hook.result.current.error).toContain('Opening project cancelled')
})

it('does not replace the model or newer error after stale validation fails', async () => {
  const pending = deferred<Model>()
  const validate = vi.fn(() => pending.promise)
  const hook = mount(undefined, validate)
  let importing!: Promise<unknown>
  await act(async () => { importing = hook.result.current.importFile(file(async () => '{"name":"imported"}')) })
  act(() => {
    hook.result.current.change({ name: 'new edit' }, 'Changed')
    hook.result.current.setError('Current error')
  })
  await act(async () => { pending.reject(new Error('Old validation error')); await importing })
  expect(hook.result.current.model.name).toBe('new edit')
  expect(hook.result.current.error).toBe('Current error')
})

it('commits only validated imports and makes them undoable', async () => {
  const validate = vi.fn(async () => ({ name: 'server-normalized' }))
  const hook = mount(undefined, validate)
  await act(async () => { await hook.result.current.importFile(file(async () => '{"name":"imported"}')) })
  expect(hook.result.current.model.name).toBe('server-normalized')
  expect(hook.result.current.busy).toBeNull()
  act(() => { hook.result.current.undo() })
  expect(hook.result.current.model.name).toBe('original')
})

it('retains the last 50 complete edits and recovers after a failed solve', async () => {
  const solve = vi.fn().mockRejectedValueOnce(new Error('Mechanism')).mockResolvedValue('valid')
  const hook = mount(solve)
  await act(async () => { await hook.result.current.run() })
  expect(hook.result.current.error).toBe('Mechanism')
  await act(async () => { await hook.result.current.run() })
  expect(hook.result.current.result).toBe('valid')
  for (let i = 1; i <= 55; i++) act(() => { hook.result.current.change({ name: String(i) }, '') })
  for (let i = 0; i < 50; i++) act(() => { hook.result.current.undo() })
  expect(hook.result.current.model.name).toBe('5')
  expect(hook.result.current.canUndo).toBe(false)
})
