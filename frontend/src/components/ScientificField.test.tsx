// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { useState } from 'react'
import { ScientificField, parseScientificNumber } from './ScientificField'
afterEach(cleanup)
it('keeps an incomplete exponent, then accepts signed scientific notation without zeroing it', () => {
  function Field() { const [value, set] = useState(-10); return <><ScientificField label="Force" value={value} onValueChange={set} /><output>{String(value)}</output></> }
  render(<Field />)
  const input = screen.getByRole('textbox', { name: 'Force' })
  fireEvent.change(input, { target: { value: '-2.5e' } })
  expect((input as HTMLInputElement).value).toBe('-2.5e')
  expect(input.getAttribute('aria-invalid')).toBe('true')
  fireEvent.change(input, { target: { value: '-2.5e+4' } })
  expect(screen.getByRole('status').textContent).toBe('-25000')
  expect(input.getAttribute('aria-invalid')).toBe('false')
  expect(Number.isNaN(parseScientificNumber('1e999'))).toBe(true)
  expect(Number.isNaN(parseScientificNumber(''))).toBe(true)
})
