import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MetricDashboard } from './Dashboard'
import { metricsFixture } from '../test/fixtures'

describe('MetricDashboard', () => {
  it('renders the six construct families', () => {
    render(<MetricDashboard metrics={metricsFixture()} />)
    expect(screen.getByText('Performance')).toBeInTheDocument()
    expect(screen.getByText('Coordination cost')).toBeInTheDocument()
    expect(screen.getByText('Quality & safety')).toBeInTheDocument()
    expect(screen.getByText('Decision')).toBeInTheDocument()
    expect(screen.getByText('Knowledge — organizational learning')).toBeInTheDocument()
    expect(screen.getByText('Resilience — turnover impact')).toBeInTheDocument()
  })

  it('renders throughput and success rate values', () => {
    render(<MetricDashboard metrics={metricsFixture()} />)
    expect(screen.getByText('85.5')).toBeInTheDocument()
    expect(screen.getByText('72.0%')).toBeInTheDocument()
    expect(screen.getByText('2.8')).toBeInTheDocument()
  })

  it('shows resilience note', () => {
    render(<MetricDashboard metrics={metricsFixture()} />)
    expect(screen.getByText('no turnover events occurred')).toBeInTheDocument()
  })
})
