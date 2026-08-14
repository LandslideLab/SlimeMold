import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { OrgChart } from './OrgChart'
import { resultFixture } from '../test/fixtures'

describe('OrgChart', () => {
  it('renders role nodes and environment header', () => {
    const result = resultFixture()
    const { container } = render(<OrgChart result={result} turn={0} messages={result.messages} />)
    const svg = container.querySelector('svg')
    expect(svg).not.toBeNull()
    expect(svg!.textContent).toContain('ENVIRONMENT')
    expect(svg!.textContent).toContain('lead')
    expect(svg!.textContent).toContain('agent1')
    expect(svg!.textContent).toContain('agent2')
  })

  it('renders reporting edges plus the environment edge', () => {
    const result = resultFixture()
    const { container } = render(<OrgChart result={result} turn={0} messages={[]} />)
    const lines = container.querySelectorAll('.edge-line')
    // agent1->lead, agent2->lead, lead->environment
    expect(lines.length).toBe(3)
  })

  it('shows a flow dot for a message at the current turn', () => {
    const result = resultFixture()
    const { container } = render(<OrgChart result={result} turn={1.5} messages={result.messages} />)
    const dots = container.querySelectorAll('.flow-dot')
    expect(dots.length).toBe(1)
  })

  it('does not render dots when the message turn is in the past', () => {
    const result = resultFixture()
    const { container } = render(<OrgChart result={result} turn={5} messages={result.messages} />)
    expect(container.querySelectorAll('.flow-dot').length).toBe(0)
  })
})
