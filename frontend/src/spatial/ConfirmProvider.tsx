import { createContext, useContext, useRef, useState, type ReactNode } from 'react'
import { Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle } from '@mui/material'
const Context = createContext<(message: string, action?: string) => Promise<boolean>>(async () => false)
export const useConfirm = () => useContext(Context)
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [request, setRequest] = useState<{ message: string; action: string } | null>(null)
  const resolver = useRef<((value: boolean) => void) | null>(null)
  const finish = (value: boolean) => { resolver.current?.(value); resolver.current = null; setRequest(null) }
  return <Context.Provider value={(message, action = 'Continue') => new Promise(resolve => {
    resolver.current?.(false); resolver.current = resolve; setRequest({ message, action })
  })}>
    {children}
    <Dialog open={!!request} onClose={() => finish(false)} aria-labelledby="confirm-title" maxWidth="xs" fullWidth>
      <DialogTitle id="confirm-title">Confirm change</DialogTitle>
      <DialogContent><DialogContentText>{request?.message}</DialogContentText></DialogContent>
      <DialogActions><Button autoFocus onClick={() => finish(false)}>Cancel</Button><Button variant="contained" onClick={() => finish(true)}>{request?.action}</Button></DialogActions>
    </Dialog>
  </Context.Provider>
}
