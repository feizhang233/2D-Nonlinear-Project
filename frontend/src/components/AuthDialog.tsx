import LockOutlinedIcon from '@mui/icons-material/LockOutlined'
import PersonAddAltOutlinedIcon from '@mui/icons-material/PersonAddAltOutlined'
import VisibilityOffRoundedIcon from '@mui/icons-material/VisibilityOffRounded'
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded'
import Alert from '@mui/material/Alert'
import Avatar from '@mui/material/Avatar'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import IconButton from '@mui/material/IconButton'
import InputAdornment from '@mui/material/InputAdornment'
import Stack from '@mui/material/Stack'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { loginAccount, registerAccount } from '../api'
import type { AuthUser } from '../domain'

export type AuthDialogMode = 'login' | 'register'

interface Props {
  open: boolean
  initialMode: AuthDialogMode
  reason?: 'save' | 'history' | null
  onClose: () => void
  onAuthenticated: (user: AuthUser, isNewAccount: boolean) => void
}

const validEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())

export function AuthDialog({ open, initialMode, reason, onClose, onAuthenticated }: Props) {
  const [mode, setMode] = useState<AuthDialogMode>(initialMode)
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const requestRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!open) return
    setMode(initialMode)
    setDisplayName('')
    setEmail('')
    setPassword('')
    setConfirmPassword('')
    setShowPassword(false)
    setError(null)
    setFieldErrors({})
  }, [initialMode, open])

  useEffect(() => () => requestRef.current?.abort(), [])

  const changeMode = (nextMode: AuthDialogMode) => {
    if (submitting) return
    setMode(nextMode)
    setPassword('')
    setConfirmPassword('')
    setError(null)
    setFieldErrors({})
  }

  const validate = () => {
    const next: Record<string, string> = {}
    if (!validEmail(email)) next.email = 'Enter a valid email address.'
    if (mode === 'register' && displayName.trim().length < 2) {
      next.displayName = 'Use at least 2 characters.'
    }
    if (password.length < (mode === 'register' ? 8 : 1)) {
      next.password = mode === 'register' ? 'Use at least 8 characters.' : 'Enter your password.'
    }
    if (mode === 'register' && password !== confirmPassword) {
      next.confirmPassword = 'Passwords do not match.'
    }
    setFieldErrors(next)
    return Object.keys(next).length === 0
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitting || !validate()) return
    setSubmitting(true)
    setError(null)
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    try {
      const session = mode === 'login'
        ? await loginAccount({ email, password }, controller.signal)
        : await registerAccount({ email, display_name: displayName, password }, controller.signal)
      if (!controller.signal.aborted && session.user) {
        onAuthenticated(session.user, mode === 'register')
      }
    } catch (requestError) {
      if (controller.signal.aborted) return
      setError(requestError instanceof Error ? requestError.message : 'Could not complete authentication.')
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null
        setSubmitting(false)
      }
    }
  }

  const passwordAdornment = (
    <InputAdornment position="end">
      <Tooltip title={showPassword ? 'Hide password' : 'Show password'}>
        <IconButton
          edge="end"
          aria-label={showPassword ? 'Hide password' : 'Show password'}
          aria-pressed={showPassword}
          onClick={() => setShowPassword((current) => !current)}
        >
          {showPassword ? <VisibilityOffRoundedIcon /> : <VisibilityRoundedIcon />}
        </IconButton>
      </Tooltip>
    </InputAdornment>
  )

  return (
    <Dialog open={open} onClose={submitting ? undefined : onClose} fullWidth maxWidth="xs">
      <Box component="form" noValidate onSubmit={submit}>
        <DialogTitle sx={{ pb: 1 }}>
          <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
            <Avatar sx={{ bgcolor: 'primary.main', width: 40, height: 40 }}>
              {mode === 'login' ? <LockOutlinedIcon /> : <PersonAddAltOutlinedIcon />}
            </Avatar>
            <Box>
              <Typography variant="h6">{mode === 'login' ? 'Welcome back' : 'Create your account'}</Typography>
              <Typography variant="body2" color="text.secondary">
                Save private model snapshots and reopen them later.
              </Typography>
            </Box>
          </Stack>
        </DialogTitle>
        <DialogContent>
          <Tabs value={mode} onChange={(_, value: AuthDialogMode) => changeMode(value)} variant="fullWidth" sx={{ mb: 2 }}>
            <Tab value="login" label="Sign in" />
            <Tab value="register" label="Register" />
          </Tabs>
          <Stack spacing={2}>
            {reason && (
              <Alert severity="info">
                {reason === 'save'
                  ? 'Sign in or register to save the model currently open in the workbench.'
                  : 'Sign in or register to access your private model history.'}
              </Alert>
            )}
            {error && <Alert severity="error" role="alert">{error}</Alert>}
            {mode === 'register' && (
              <TextField
                autoFocus
                required
                label="Display name"
                value={displayName}
                error={Boolean(fieldErrors.displayName)}
                helperText={fieldErrors.displayName}
                slotProps={{ htmlInput: { minLength: 2, maxLength: 120, autoComplete: 'name' } }}
                onChange={(event) => { setDisplayName(event.target.value); setFieldErrors((current) => ({ ...current, displayName: '' })); setError(null) }}
              />
            )}
            <TextField
              autoFocus={mode === 'login'}
              required
              type="email"
              label="Email"
              value={email}
              error={Boolean(fieldErrors.email)}
              helperText={fieldErrors.email}
              slotProps={{ htmlInput: { maxLength: 320, autoComplete: 'email' } }}
              onChange={(event) => { setEmail(event.target.value); setFieldErrors((current) => ({ ...current, email: '' })); setError(null) }}
            />
            <TextField
              required
              type={showPassword ? 'text' : 'password'}
              label="Password"
              value={password}
              error={Boolean(fieldErrors.password)}
              helperText={fieldErrors.password || (mode === 'register' ? 'Use at least 8 characters.' : undefined)}
              slotProps={{
                htmlInput: { minLength: mode === 'register' ? 8 : 1, maxLength: 128, autoComplete: mode === 'register' ? 'new-password' : 'current-password' },
                input: { endAdornment: passwordAdornment },
              }}
              onChange={(event) => { setPassword(event.target.value); setFieldErrors((current) => ({ ...current, password: '' })); setError(null) }}
            />
            {mode === 'register' && (
              <TextField
                required
                type={showPassword ? 'text' : 'password'}
                label="Confirm password"
                value={confirmPassword}
                error={Boolean(fieldErrors.confirmPassword)}
                helperText={fieldErrors.confirmPassword}
                slotProps={{
                  htmlInput: { minLength: 8, maxLength: 128, autoComplete: 'new-password' },
                  input: { endAdornment: passwordAdornment },
                }}
                onChange={(event) => { setConfirmPassword(event.target.value); setFieldErrors((current) => ({ ...current, confirmPassword: '' })); setError(null) }}
              />
            )}
            <Alert severity="info" variant="outlined" icon={false}>
              Guest mode includes modeling, meshing, analysis, import, and export. Guest work is not saved to model history.
            </Alert>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button onClick={onClose} disabled={submitting} color="inherit">Continue as guest</Button>
          <Button type="submit" variant="contained" disabled={submitting} sx={{ minWidth: 132 }}>
            {submitting ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  )
}
