import { useCallback, useEffect, useRef, useState } from 'react'
import { getSession, logoutAccount } from '../api'
import type { AuthUser } from '../domain'

type MessageTone = 'success' | 'info' | 'warning' | 'error'

export function useIdentity(showMessage: (message: string, severity: MessageTone) => void) {
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const restoreControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    restoreControllerRef.current = controller
    void getSession(controller.signal)
      .then((session) => {
        if (!controller.signal.aborted) setCurrentUser(session.user)
      })
      .catch((error) => {
        if (controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) return
        setCurrentUser(null)
        showMessage('Account service is unavailable. Continuing in guest mode.', 'warning')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => {
      controller.abort()
      if (restoreControllerRef.current === controller) restoreControllerRef.current = null
    }
  }, [showMessage])

  const authenticated = useCallback((user: AuthUser, isNewAccount: boolean) => {
    restoreControllerRef.current?.abort()
    restoreControllerRef.current = null
    setCurrentUser(user)
    setLoading(false)
    showMessage(
      isNewAccount
        ? `Welcome, ${user.display_name}. Your account is ready.`
        : `Welcome back, ${user.display_name}.`,
      'success',
    )
  }, [showMessage])

  const sessionExpired = useCallback(() => {
    restoreControllerRef.current?.abort()
    restoreControllerRef.current = null
    setCurrentUser(null)
    showMessage('Your session expired. Your current model is still open in guest mode.', 'warning')
  }, [showMessage])

  const signOut = useCallback(async (): Promise<boolean> => {
    try {
      restoreControllerRef.current?.abort()
      restoreControllerRef.current = null
      await logoutAccount()
      setCurrentUser(null)
      showMessage('Signed out. You can keep working in guest mode.', 'success')
      return true
    } catch (error) {
      showMessage(error instanceof Error ? error.message : 'Could not sign out.', 'error')
      return false
    }
  }, [showMessage])

  return { currentUser, loading, authenticated, sessionExpired, signOut }
}
