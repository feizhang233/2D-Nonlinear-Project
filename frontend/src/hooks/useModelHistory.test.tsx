// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { listSavedModels, saveModelSnapshot } from '../api'
import type { AuthUser, SavedModel } from '../domain'
import { cloneSampleModel } from '../sampleModel'
import { useModelHistory } from './useModelHistory'
vi.mock('../api', async (original) => ({ ...await original<typeof import('../api')>(), listSavedModels: vi.fn(), saveModelSnapshot: vi.fn() }))
const user: AuthUser = { id: 'engineer', display_name: 'Engineer', email: 'engineer@example.com', created_at: '' }
const entry: SavedModel = { id: 'new-snapshot', name: 'Test', model_family: 'frame', model: cloneSampleModel(), saved_at: '' }
const options = { showMessage: vi.fn(), onSessionExpired: vi.fn() }
afterEach(() => { cleanup(); vi.resetAllMocks() })

describe('history request ordering', () => {
  it('does not let an earlier list request erase a newly saved snapshot', async () => {
    let resolveList!: (items: SavedModel[]) => void
    vi.mocked(listSavedModels).mockReturnValue(new Promise((resolve) => { resolveList = resolve }))
    vi.mocked(saveModelSnapshot).mockResolvedValue(entry)
    const { result } = renderHook(() => useModelHistory(user, options))
    await act(async () => { await result.current.save(entry.model) })
    await act(async () => { resolveList([]) })
    expect(result.current.entries).toEqual([entry])
  })

  it('clears a pending save indicator after sign-out without exposing old history', async () => {
    let resolveSave!: (item: SavedModel) => void
    vi.mocked(listSavedModels).mockResolvedValue([])
    vi.mocked(saveModelSnapshot).mockReturnValue(new Promise((resolve) => { resolveSave = resolve }))
    const { result, rerender } = renderHook(({ account }: { account: AuthUser | null }) => useModelHistory(account, options), { initialProps: { account: user as AuthUser | null } })
    act(() => { void result.current.save(entry.model) })
    rerender({ account: null })
    await act(async () => { resolveSave(entry) })
    expect(result.current.saving).toBe(false)
    expect(result.current.entries).toEqual([])
  })
})
