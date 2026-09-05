import { useCallback, useEffect, useRef, useState } from 'react'
import { deleteSavedModel, listSavedModels, saveModelSnapshot, StudioApiError } from '../api'
import type { AuthUser, ModelInput, SavedModel } from '../domain'

type MessageTone = 'success' | 'info' | 'warning' | 'error'

interface Options {
  showMessage: (message: string, severity: MessageTone) => void
  onSessionExpired: () => void
}

interface HistoryState {
  ownerId: string | null
  entries: SavedModel[]
}

export function useModelHistory(currentUser: AuthUser | null, options: Options) {
  const { showMessage, onSessionExpired } = options
  const [state, setState] = useState<HistoryState>({ ownerId: null, entries: [] })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const savingRef = useRef(false)
  const deletingRef = useRef(false)
  const mutationVersionRef = useRef(0)
  const ownerRef = useRef<string | null>(currentUser?.id ?? null)
  ownerRef.current = currentUser?.id ?? null
  const ownerId = currentUser?.id ?? null
  const entries = state.ownerId === ownerId ? state.entries : []

  const requestFailed = useCallback((error: unknown, fallback: string) => {
    if (error instanceof StudioApiError && error.status === 401) {
      onSessionExpired()
      return
    }
    showMessage(error instanceof Error ? error.message : fallback, 'error')
  }, [onSessionExpired, showMessage])

  const refresh = useCallback(async (signal?: AbortSignal) => {
    const requestedOwner = ownerRef.current
    if (!requestedOwner) {
      setState({ ownerId: null, entries: [] })
      return
    }
    setLoading(true)
    const version = mutationVersionRef.current
    try {
      const saved = await listSavedModels(signal)
      if (signal?.aborted || ownerRef.current !== requestedOwner || mutationVersionRef.current !== version) return
      setState({ ownerId: requestedOwner, entries: saved })
    } catch (error) {
      if (signal?.aborted || (error instanceof DOMException && error.name === 'AbortError')) return
      if (ownerRef.current === requestedOwner) requestFailed(error, 'Could not load model history.')
    } finally {
      if (!signal?.aborted && ownerRef.current === requestedOwner) setLoading(false)
    }
  }, [requestFailed])

  useEffect(() => {
    if (!ownerId) {
      setState({ ownerId: null, entries: [] })
      setLoading(false)
      return
    }
    const controller = new AbortController()
    setState({ ownerId, entries: [] })
    void refresh(controller.signal)
    return () => controller.abort()
  }, [ownerId, refresh])

  const save = useCallback(async (model: ModelInput): Promise<SavedModel | null> => {
    const requestedOwner = ownerRef.current
    if (!requestedOwner || savingRef.current) return null
    savingRef.current = true
    setSaving(true)
    try {
      const entry = await saveModelSnapshot(model, model.name.trim() || 'Untitled model')
      if (ownerRef.current !== requestedOwner) return null
      mutationVersionRef.current += 1
      setState((current) => ({
        ownerId: requestedOwner,
        entries: [entry, ...(current.ownerId === requestedOwner ? current.entries : [])]
          .filter((item, index, values) => values.findIndex(({ id }) => id === item.id) === index)
          .slice(0, 24),
      }))
      showMessage(`Saved “${entry.name}” to your model history.`, 'success')
      return entry
    } catch (error) {
      if (ownerRef.current === requestedOwner) requestFailed(error, 'Could not save this model.')
      return null
    } finally {
      savingRef.current = false
      setSaving(false)
    }
  }, [requestFailed, showMessage])

  const remove = useCallback(async (entry: SavedModel): Promise<boolean> => {
    const requestedOwner = ownerRef.current
    if (!requestedOwner || deletingRef.current) return false
    deletingRef.current = true
    setDeletingId(entry.id)
    try {
      await deleteSavedModel(entry.id)
      if (ownerRef.current !== requestedOwner) return false
      mutationVersionRef.current += 1
      setState((current) => current.ownerId === requestedOwner
        ? { ...current, entries: current.entries.filter((item) => item.id !== entry.id) }
        : current)
      showMessage(`Deleted “${entry.name}” from model history.`, 'success')
      return true
    } catch (error) {
      if (ownerRef.current === requestedOwner) requestFailed(error, 'Could not delete this saved model.')
      return false
    } finally {
      deletingRef.current = false
      setDeletingId(null)
    }
  }, [requestFailed, showMessage])

  return { entries, loading, saving, deletingId, refresh, save, remove }
}
