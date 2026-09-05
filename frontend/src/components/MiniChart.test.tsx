// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { MiniChart } from './MiniChart'
afterEach(cleanup)
it('breaks chart segments at non-finite samples without emitting invalid SVG coordinates', () => {
  const { container } = render(<MiniChart title="Convergence" xLabel="Step" yLabel="Residual" series={[{ name: 'Residual', color: '#0f766e', points: [{ x: 0, y: 1 }, { x: 1, y: NaN }, { x: 2, y: 0.1 }] }]} />)
  const path = container.querySelector('path')!.getAttribute('d')!
  expect(path).not.toContain('NaN')
  expect(path.match(/M/g)).toHaveLength(2)
})
