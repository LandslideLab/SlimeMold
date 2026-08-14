import { describe, expect, it, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ScanPanel } from './ScanPanel'
import { hierarchySpec } from '../defaults'
import type { ScanResult } from '../types'

const scanResult: ScanResult = {
  mode: 'scan',
  parameter: 'taskflow.arrival_rate',
  path: 'taskflow.arrival_rate',
  values: [0.5, 1.0, 2.0],
  metric: 'throughput',
  metric_values: [10, 25, 60],
  seeds: [7, 8, 9],
  spec_template: hierarchySpec(),
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ScanPanel', () => {
  it('renders knob presets and dot-path input', () => {
    render(<ScanPanel currentSpec={hierarchySpec()} />)
    expect(screen.getByLabelText('knob')).toBeInTheDocument()
    expect(screen.getByLabelText('dot-path')).toBeInTheDocument()
  })

  it('runs a scan and renders the sensitivity table', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        status: 200,
        text: async () => JSON.stringify(scanResult),
      })),
    )
    const user = userEvent.setup()
    render(<ScanPanel currentSpec={hierarchySpec()} />)
    await user.click(screen.getByRole('button', { name: /Scan/ }))
    expect((await screen.findAllByText('10')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('60').length).toBeGreaterThan(0)
    expect(screen.getAllByText('throughput').length).toBeGreaterThan(0)
  })

  it('shows an engine error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 400,
        text: async () => JSON.stringify({ error: 'unknown metric: nope' }),
      })),
    )
    const user = userEvent.setup()
    render(<ScanPanel currentSpec={hierarchySpec()} />)
    await user.click(screen.getByRole('button', { name: /Scan/ }))
    expect(await screen.findByText('unknown metric: nope')).toBeInTheDocument()
  })
})
