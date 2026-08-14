import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { hierarchySpec } from './defaults'

vi.mock('./api', () => ({
  isEngineReachable: vi.fn(async () => true),
  fetchHealth: vi.fn(async () => ({ status: 'ok', engine_version: '0.1.0' })),
  fetchExampleSpec: vi.fn(async () => hierarchySpec()),
  simulate: vi.fn(),
  compare: vi.fn(),
  scan: vi.fn(),
  oddReport: vi.fn(),
}))

describe('App', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('renders the masthead and all tabs', async () => {
    render(<App />)
    expect(await screen.findByText('SlimeMold')).toBeInTheDocument()
    for (const tab of ['Design', 'Run', 'Compare', 'Scan', 'Export']) {
      expect(screen.getByRole('button', { name: tab })).toBeInTheDocument()
    }
  })

  it('shows the designer view by default', async () => {
    render(<App />)
    expect(await screen.findByText('Organization designer')).toBeInTheDocument()
    expect(await screen.findByText('Reporting topology')).toBeInTheDocument()
  })

  it('switches to the Compare tab', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByText('Organization designer')
    await user.click(screen.getByRole('button', { name: 'Compare' }))
    expect(screen.getByText(/Design A vs Design B/)).toBeInTheDocument()
  })

  it('switches to the Export tab', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByText('Organization designer')
    await user.click(screen.getByRole('button', { name: 'Export' }))
    expect(screen.getByText(/Export an ABM-compliant reproduction package/)).toBeInTheDocument()
  })
})
