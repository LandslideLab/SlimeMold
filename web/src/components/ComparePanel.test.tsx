import { describe, expect, it, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ComparePanel } from './ComparePanel'
import { hierarchySpec } from '../defaults'
import type { CompareResult } from '../types'

const compareResult: CompareResult = {
  mode: 'compare',
  metric: 'throughput',
  reps: 3,
  values_a: [10, 12, 14],
  values_b: [8, 9, 10],
  statistics: {
    mean_a: 12,
    sd_a: 2,
    mean_b: 9,
    sd_b: 1,
    cohens_d: 1.8,
    test: 'mann_whitney_u',
    u: 9,
    z: -1.09,
    p: 0.1,
    significant: false,
  },
  seeds: [1, 2, 3],
  spec_a: hierarchySpec(),
  spec_b: hierarchySpec(),
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ComparePanel', () => {
  it('renders both design slots', () => {
    render(<ComparePanel currentSpec={hierarchySpec()} />)
    expect(screen.getByText('Design A')).toBeInTheDocument()
    expect(screen.getByText('Design B')).toBeInTheDocument()
  })

  it('runs a comparison and renders statistics', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        status: 200,
        text: async () => JSON.stringify(compareResult),
      })),
    )
    const user = userEvent.setup()
    render(<ComparePanel currentSpec={hierarchySpec()} />)
    await user.click(screen.getByRole('button', { name: /Compare/ }))
    expect(await screen.findByText('NOT SIGNIFICANT')).toBeInTheDocument()
    expect(screen.getByText('Mean A')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('p-value')).toBeInTheDocument()
  })

  it('shows an error when the engine rejects', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 400,
        text: async () => JSON.stringify({ error: 'bad spec' }),
      })),
    )
    const user = userEvent.setup()
    render(<ComparePanel currentSpec={hierarchySpec()} />)
    await user.click(screen.getByRole('button', { name: /Compare/ }))
    expect(await screen.findByText('bad spec')).toBeInTheDocument()
  })
})
