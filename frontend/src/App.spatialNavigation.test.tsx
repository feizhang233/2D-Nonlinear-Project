// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from './App'
import { studioTheme } from './theme'

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} unobserve() {} })
  Object.defineProperty(window, 'localStorage', { configurable: true, value: {
    getItem: (key: string) => key === 'nonlinear-studio-guide-hidden-v2' ? 'true' : null,
    setItem: vi.fn(),
  } })
  vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
    if (String(input).endsWith('/api/v1/auth/session'))
      return Response.json({ authenticated: false, user: null })
    throw new Error(`Unexpected request: ${String(input)}`)
  })
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

it.each(['Frame', 'Continuum', 'Plate', 'Shell'])(
  'keeps the %s family selected across both dimension transitions', family => {
    render(<ThemeProvider theme={studioTheme}><App /></ThemeProvider>)
    fireEvent.click(screen.getByRole('button', { name: '3D' }))
    fireEvent.click(screen.getByRole('tab', { name: `${family} 3D workspace` }))
    fireEvent.click(screen.getByRole('button', { name: '2D' }))
    expect(screen.getByRole('tab', { name: `${family} workspace` })
      .getAttribute('aria-selected')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: '3D' }))
    expect(screen.getByRole('tab', { name: `${family} 3D workspace` })
      .getAttribute('aria-selected')).toBe('true')
  },
)
