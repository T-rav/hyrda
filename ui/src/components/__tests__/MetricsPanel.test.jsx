import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MetricsPanel } from '../MetricsPanel'

describe('MetricsPanel', () => {
  it('renders lifetime stats as cards', () => {
    const metrics = {
      lifetime: { issues_completed: 10, prs_merged: 8, issues_created: 3 },
      rates: { merge_rate: 0.8 },
    }
    render(<MetricsPanel metrics={metrics} lifetimeStats={null} />)
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('Issues Completed')).toBeInTheDocument()
    expect(screen.getByText('PRs Merged')).toBeInTheDocument()
    expect(screen.getByText('Issues Created')).toBeInTheDocument()
  })

  it('shows 0 values gracefully when no data', () => {
    render(<MetricsPanel metrics={null} lifetimeStats={null} />)
    const zeros = screen.getAllByText('0')
    expect(zeros.length).toBe(3)
  })

  it('shows rates when metrics data includes them', () => {
    const metrics = {
      lifetime: { issues_completed: 10, prs_merged: 8, issues_created: 0 },
      rates: { merge_rate: 0.8 },
    }
    render(<MetricsPanel metrics={metrics} lifetimeStats={null} />)
    expect(screen.getByText('80%')).toBeInTheDocument()
    expect(screen.getByText('merge rate')).toBeInTheDocument()
  })

  it('does not show rates section when no rates', () => {
    const metrics = {
      lifetime: { issues_completed: 0, prs_merged: 0, issues_created: 0 },
      rates: {},
    }
    render(<MetricsPanel metrics={metrics} lifetimeStats={null} />)
    expect(screen.queryByText('Rates')).not.toBeInTheDocument()
  })

  it('falls back to lifetimeStats when metrics is null', () => {
    const lifetimeStats = { issues_completed: 5, prs_merged: 3, issues_created: 1 }
    render(<MetricsPanel metrics={null} lifetimeStats={lifetimeStats} />)
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('shows empty state message when both metrics and lifetimeStats are null', () => {
    render(<MetricsPanel metrics={null} lifetimeStats={null} />)
    expect(screen.getByText('No metrics data available yet.')).toBeInTheDocument()
  })
})
