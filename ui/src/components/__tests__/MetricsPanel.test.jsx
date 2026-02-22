import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

const { mockState } = vi.hoisted(() => ({
  mockState: {
    metrics: null,
    lifetimeStats: null,
    githubMetrics: null,
    metricsHistory: null,
    sessionTriaged: 0,
    sessionPlanned: 0,
    sessionImplemented: 0,
    sessionReviewed: 0,
    mergedCount: 0,
  },
}))

vi.mock('../../context/HydraContext', () => ({
  useHydra: () => mockState,
}))

function resetMockState() {
  mockState.metrics = null
  mockState.lifetimeStats = null
  mockState.githubMetrics = null
  mockState.metricsHistory = null
  mockState.sessionTriaged = 0
  mockState.sessionPlanned = 0
  mockState.sessionImplemented = 0
  mockState.sessionReviewed = 0
  mockState.mergedCount = 0
}

beforeEach(() => {
  resetMockState()
})

describe('MetricsPanel', () => {
  it('shows empty state message when no data at all', async () => {
    const { MetricsPanel } = await import('../MetricsPanel')
    render(<MetricsPanel />)
    expect(screen.getByText('No metrics data available yet.')).toBeInTheDocument()
  })

  it('renders lifetime stats from GitHub metrics', async () => {
    mockState.githubMetrics = {
      open_by_label: { 'hydra-plan': 2, 'hydra-ready': 1, 'hydra-review': 0, 'hydra-hitl': 0, 'hydra-fixed': 0 },
      total_closed: 10,
      total_merged: 8,
    }
    const { MetricsPanel } = await import('../MetricsPanel')
    render(<MetricsPanel />)
    expect(screen.getByText('Lifetime')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
    expect(screen.getByText('Issues Completed')).toBeInTheDocument()
    expect(screen.getByText('PRs Merged')).toBeInTheDocument()
  })

  it('shows open issues count from GitHub metrics', async () => {
    mockState.githubMetrics = {
      open_by_label: { 'hydra-plan': 3, 'hydra-ready': 2, 'hydra-review': 1, 'hydra-hitl': 0, 'hydra-fixed': 0 },
      total_closed: 5,
      total_merged: 4,
    }
    const { MetricsPanel } = await import('../MetricsPanel')
    render(<MetricsPanel />)
    expect(screen.getByText('Open Issues')).toBeInTheDocument()
    expect(screen.getByText('6')).toBeInTheDocument() // 3+2+1
  })

  it('renders session stats when session has activity', async () => {
    mockState.sessionTriaged = 3
    mockState.sessionPlanned = 2
    mockState.sessionImplemented = 1
    mockState.sessionReviewed = 1
    mockState.mergedCount = 0
    mockState.githubMetrics = {
      open_by_label: {},
      total_closed: 0,
      total_merged: 0,
    }
    const { MetricsPanel } = await import('../MetricsPanel')
    render(<MetricsPanel />)
    expect(screen.getByText('Session')).toBeInTheDocument()
    expect(screen.getByText('Triaged')).toBeInTheDocument()
    expect(screen.getByText('Planned')).toBeInTheDocument()
    expect(screen.getByText('Implemented')).toBeInTheDocument()
    expect(screen.getByText('Reviewed')).toBeInTheDocument()
    expect(screen.getByText('Merged')).toBeInTheDocument()
  })

  it('does not render session section when all session counts are zero', async () => {
    mockState.githubMetrics = {
      open_by_label: {},
      total_closed: 5,
      total_merged: 3,
    }
    const { MetricsPanel } = await import('../MetricsPanel')
    render(<MetricsPanel />)
    expect(screen.queryByText('Session')).not.toBeInTheDocument()
  })

  it('renders pipeline blocks visualization with GitHub metrics', async () => {
    mockState.githubMetrics = {
      open_by_label: { 'hydra-plan': 3, 'hydra-ready': 1, 'hydra-review': 2, 'hydra-hitl': 0, 'hydra-fixed': 0 },
      total_closed: 0,
      total_merged: 0,
    }
    const { MetricsPanel } = await import('../MetricsPanel')
    render(<MetricsPanel />)
    expect(screen.getByText('Pipeline')).toBeInTheDocument()
    expect(screen.getByText('Plan')).toBeInTheDocument()
    expect(screen.getByText('Ready')).toBeInTheDocument()
    expect(screen.getByText('Review')).toBeInTheDocument()
    expect(screen.getByText('HITL')).toBeInTheDocument()
    expect(screen.getByText('Fixed')).toBeInTheDocument()
  })

  it('falls back to lifetimeStats when metrics and githubMetrics are null', async () => {
    mockState.lifetimeStats = { issues_completed: 5, prs_merged: 3, issues_created: 1 }
    const { MetricsPanel } = await import('../MetricsPanel')
    render(<MetricsPanel />)
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('falls back to metrics.lifetime when githubMetrics is null', async () => {
    mockState.metrics = {
      lifetime: { issues_completed: 10, prs_merged: 8, issues_created: 3 },
      rates: {},
    }
    const { MetricsPanel } = await import('../MetricsPanel')
    render(<MetricsPanel />)
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
  })

  it('renders rates section when metricsHistory has current snapshot', async () => {
    mockState.metricsHistory = {
      current: { merge_rate: 0.8, first_pass_approval_rate: 0.6, quality_fix_rate: 0.1, hitl_escalation_rate: 0.05, issues_completed: 10, prs_merged: 8 },
      snapshots: [],
    }
    const { MetricsPanel } = await import('../MetricsPanel')
    render(<MetricsPanel />)
    expect(screen.getByText('Rates')).toBeInTheDocument()
    expect(screen.getByText('Merge Rate')).toBeInTheDocument()
    expect(screen.getByText('First-Pass Approval')).toBeInTheDocument()
  })
})
