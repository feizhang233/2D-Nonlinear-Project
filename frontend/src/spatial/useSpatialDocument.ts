import { useEffect, useRef, useState } from 'react'
import { downloadJson } from '../projectFiles'
import { readBrowserStorage, writeBrowserStorage } from './browserStorage'
/** Portable spatial documents: atomic imports, bounded history and stale-result cancellation. */
export function useSpatialDocument<M, R>({
  storage,
  example,
  parse,
  solve,
  validate,
  active,
}: {
  storage: string
  example: () => M
  parse: (v: unknown) => M
  solve: (m: M, s: AbortSignal) => Promise<R>
  validate: (m: M, s: AbortSignal) => Promise<M>
  active: boolean
}) {
  const [initial] = useState(() => {
    try {
      const raw = readBrowserStorage(storage)
      return { model: raw ? parse(JSON.parse(raw)) : example(), warning: '' }
    } catch {
      return {
        model: example(),
        warning:
          'Saved project could not be read. An example is shown; storage is unchanged until your next edit.',
      }
    }
  })
  const [model, setModel] = useState(initial.model),
    [result, setResult] = useState<R | null>(null)
  const [warning, setWarning] = useState(initial.warning),
    [error, setError] = useState(''),
    [message, setMessage] = useState('')
  const [past, setPast] = useState<M[]>([]),
    [future, setFuture] = useState<M[]>([]),
    [busy, setBusy] = useState<'solve' | 'import' | null>(null)
  const abort = useRef<AbortController | null>(null),
    revision = useRef(0)
  const persist = (m: M) =>
    setWarning(
      writeBrowserStorage(storage, JSON.stringify(m))
        ? ''
        : 'Local saving is unavailable. Save project to keep a portable copy.',
    )
  const invalidate = () => {
    revision.current++
    abort.current?.abort()
    abort.current = null
    setBusy(null)
    setResult(null)
    setError('')
  }
  const change = (next: M, note: string) => {
    const checked = parse(next)
    invalidate()
    setPast((v) => [...v.slice(-49), model])
    setFuture([])
    setModel(checked)
    persist(checked)
    setMessage(note)
    return checked
  }
  const undo = () => {
    const next = past.at(-1)
    if (!next) return
    invalidate()
    setPast((v) => v.slice(0, -1))
    setFuture((v) => [model, ...v])
    setModel(next)
    persist(next)
    return next
  }
  const redo = () => {
    const next = future[0]
    if (!next) return
    invalidate()
    setFuture((v) => v.slice(1))
    setPast((v) => [...v, model])
    setModel(next)
    persist(next)
    return next
  }
  const cancel = () => {
    revision.current++
    abort.current?.abort()
    abort.current = null
    setBusy(null)
    setError(busy === 'import' ? 'Opening project cancelled. The current model is unchanged.'
      : 'Stopped waiting. The server may still be finishing this analysis.')
  }
  const run = async () => {
    if (!active || abort.current) return
    const controller = new AbortController(),
      version = revision.current
    abort.current = controller
    setBusy('solve')
    setError('')
    setResult(null)
    try {
      const response = await solve(model, controller.signal)
      if (!controller.signal.aborted && version === revision.current) {
        setResult(response)
        setMessage('Analysis complete. Review results and numerical checks.')
        return response
      }
    } catch (e) {
      if (!controller.signal.aborted && version === revision.current)
        setError(e instanceof Error ? e.message : 'Analysis failed.')
    } finally {
      if (abort.current === controller) {
        abort.current = null
        setBusy(null)
      }
    }
  }
  const importFile = async (file: File) => {
    if (!active || abort.current) return
    const controller = new AbortController(),
      version = revision.current
    abort.current = controller
    setBusy('import')
    setError('')
    try {
      if (file.size > 5 * 1024 * 1024)
        throw new Error('Open a project JSON file smaller than 5 MB.')
      const text = await file.text()
      if (controller.signal.aborted || version !== revision.current) return
      const candidate = parse(JSON.parse(text))
      const checked = await validate(candidate, controller.signal)
      if (!controller.signal.aborted && version === revision.current)
        return change(
          checked,
          'Project opened. Undo restores the previous model.',
        )
    } catch (e) {
      if (!controller.signal.aborted && version === revision.current)
        setError(e instanceof Error ? e.message : 'Unable to open project.')
    } finally {
      if (abort.current === controller) {
        abort.current = null
        setBusy(null)
      }
    }
  }
  const exportFile = (filename: string) => {
    downloadJson(model, filename)
    persist(model)
    setMessage('Project exported')
  }
  useEffect(() => {
    if (!active && abort.current) {
      revision.current++
      abort.current.abort()
      abort.current = null
      setBusy(null)
      setError(busy === 'import'
        ? 'Opening project cancelled after switching workspace. The current model is unchanged.'
        : 'Analysis display cancelled after switching workspace. Run again for a new result.')
    }
  }, [active])
  useEffect(
    () => () => {
      abort.current?.abort()
    },
    [],
  )
  return {
    model,
    result,
    warning,
    error,
    message,
    setError,
    setMessage,
    change,
    undo,
    redo,
    canUndo: !!past.length,
    canRedo: !!future.length,
    busy,
    cancel,
    run,
    importFile,
    exportFile,
  }
}
