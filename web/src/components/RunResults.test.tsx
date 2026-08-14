import { describe, expect, it, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RunResults } from './RunResults'
import { resultFixture } from '../test/fixtures'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('RunResults', () => {
  it('renders run summary and metrics', () => {
    const result = resultFixture()
    render(<RunResults result={result} />)
    expect(screen.getByText(/Run complete/)).toBeInTheDocument()
    expect(screen.getByText('85.5')).toBeInTheDocument()
    expect(screen.getByText('T1-1')).toBeInTheDocument()
  })

  it('renders the org chart animation player', () => {
    const result = resultFixture()
    render(<RunResults result={result} />)
    expect(screen.getByText(/Run trajectory/)).toBeInTheDocument()
    const svg = document.querySelector('svg')
    expect(svg).not.toBeNull()
  })

  it('downloads ODD report from the engine', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ odd: 'ODD Protocol Description -- SlimeMold' }),
      })),
    )
    const create = vi.fn(() => 'blob:mock')
    const revoke = vi.fn()
    vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: revoke })
    const realCreateElement = document.createElement.bind(document)
    document.createElement = vi.fn((tag: string) => {
      const el = realCreateElement(tag)
      el.click = vi.fn()
      return el
    }) as unknown as typeof document.createElement

    const user = userEvent.setup()
    render(<RunResults result={resultFixture()} />)
    await user.click(screen.getByRole('button', { name: /ODD report/ }))
    expect(await screen.findByText(/ODD protocol report downloaded/)).toBeInTheDocument()
  })

  it('toggles the event log', async () => {
    const user = userEvent.setup()
    render(<RunResults result={resultFixture()} />)
    await user.click(screen.getByRole('button', { name: /Show events/ }))
    expect(screen.getByText('org -> agent1 [assign]')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Hide events/ }))
    expect(screen.queryByText('org -> agent1 [assign]')).not.toBeInTheDocument()
  })
})
