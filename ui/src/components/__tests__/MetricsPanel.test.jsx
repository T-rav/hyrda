import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MetricsPanel } from '../MetricsPanel'

describe('MetricsPanel', () => {
  it('shows empty state message when no data at all', () => {
    render(<MetricsPanel metrics={null} lifetimeStats={null} githubMetrics={null} sessionCounts={{}} />)
    expect(screen.getByText('No metrics data available yet.')).toBeInTheDocument()
  })

  it('renders lifetime stats from GitHub metrics', () => {
    const githubMetrics = {
      open_by_label: { 'hydra-plan': 2, 'hydra-ready': 1, 'hydra-review': 0, 'hydra-hitl': 0, 'hydra-fixed': 0 },
      total_closed: 10,
      total_merged: 8,
    }
    render(<MetricsPanel metrics={null} lifetimeStats={null} githubMetrics={githubMetrics} sessionCounts={{}} />)
    expect(screen.getByText('Lifetime')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
    expect(screen.getByText('Issues Completed')).toBeInTheDocument()
    expect(screen.getByText('PRs Merged')).toBeInTheDocument()
  })

  it('shows open issues count from GitHub metrics', () => {
    const githubMetrics = {
      open_by_label: { 'hydra-plan': 3, 'hydra-ready': 2, 'hydra-review': 1, 'hydra-hitl': 0, 'hydra-fixed': 0 },
      total_closed: 5,
      total_merged: 4,
    }
    render(<MetricsPanel metrics={null} lifetimeStats={null} githubMetrics={githubMetrics} sessionCounts={{}} />)
    expect(screen.getByText('Open Issues')).toBeInTheDocument()
    expect(screen.getByText('6')).toBeInTheDocument() // 3+2+1
  })

  it('renders session stats when session has activity', () => {
    const sessionCounts = { triaged: 3, planned: 2, implemented: 1, reviewed: 1, merged: 0 }
    const githubMetrics = {
      open_by_label: {},
      total_closed: 0,
      total_merged: 0,
    }
    render(<MetricsPanel metrics={null} lifetimeStats={null} githubMetrics={githubMetrics} sessionCounts={sessionCounts} />)
    expect(screen.getByText('Session')).toBeInTheDocument()
    expect(screen.getByText('Triaged')).toBeInTheDocument()
    expect(screen.getByText('Planned')).toBeInTheDocument()
    expect(screen.getByText('Implemented')).toBeInTheDocument()
  })

  it('does not render session section when all session counts are zero', () => {
    const githubMetrics = {
      open_by_label: {},
      total_closed: 5,
      total_merged: 3,
    }
    render(<MetricsPanel metrics={null} lifetimeStats={null} githubMetrics={githubMetrics} sessionCounts={{ triaged: 0, planned: 0, implemented: 0, reviewed: 0, merged: 0 }} />)
    expect(screen.queryByText('Session')).not.toBeInTheDocument()
  })

  it('renders pipeline blocks visualization with GitHub metrics', () => {
    const githubMetrics = {
      open_by_label: { 'hydra-plan': 3, 'hydra-ready': 1, 'hydra-review': 2, 'hydra-hitl': 0, 'hydra-fixed': 0 },
      total_closed: 0,
      total_merged: 0,
    }
    render(<MetricsPanel metrics={null} lifetimeStats={null} githubMetrics={githubMetrics} sessionCounts={{}} />)
    expect(screen.getByText('Pipeline')).toBeInTheDocument()
    expect(screen.getByText('Plan')).toBeInTheDocument()
    expect(screen.getByText('Ready')).toBeInTheDocument()
    expect(screen.getByText('Review')).toBeInTheDocument()
    expect(screen.getByText('HITL')).toBeInTheDocument()
    expect(screen.getByText('Fixed')).toBeInTheDocument()
  })

  it('falls back to lifetimeStats when metrics and githubMetrics are null', () => {
    const lifetimeStats = { issues_completed: 5, prs_merged: 3, issues_created: 1 }
    render(<MetricsPanel metrics={null} lifetimeStats={lifetimeStats} githubMetrics={null} sessionCounts={{}} />)
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('falls back to metrics.lifetime when githubMetrics is null', () => {
    const metrics = {
      lifetime: { issues_completed: 10, prs_merged: 8, issues_created: 3 },
      rates: {},
    }
    render(<MetricsPanel metrics={metrics} lifetimeStats={null} githubMetrics={null} sessionCounts={{}} />)
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
  })

  it('shows empty state when everything is null and session is empty', () => {
    render(<MetricsPanel metrics={null} lifetimeStats={null} githubMetrics={null} sessionCounts={null} />)
    expect(screen.getByText('No metrics data available yet.')).toBeInTheDocument()
  })
})

describe('MetricsPanel background worker toggles', () => {
  const githubMetrics = {
    open_by_label: {},
    total_closed: 5,
    total_merged: 3,
  }

  it('renders Background Workers section when onToggleBgWorker is provided', () => {
    render(
      <MetricsPanel
        metrics={null} lifetimeStats={null} githubMetrics={githubMetrics}
        sessionCounts={{}} backgroundWorkers={[]} onToggleBgWorker={() => {}}
      />
    )
    expect(screen.getByText('Background Workers')).toBeInTheDocument()
    expect(screen.getByText('Memory Sync')).toBeInTheDocument()
    expect(screen.getByText('Retrospective')).toBeInTheDocument()
    expect(screen.getByText('Metrics')).toBeInTheDocument()
    expect(screen.getByText('Review Insights')).toBeInTheDocument()
  })

  it('does not render Background Workers section without onToggleBgWorker', () => {
    render(
      <MetricsPanel
        metrics={null} lifetimeStats={null} githubMetrics={githubMetrics}
        sessionCounts={{}}
      />
    )
    expect(screen.queryByText('Background Workers')).not.toBeInTheDocument()
  })

  it('toggle button calls onToggleBgWorker with correct worker key', () => {
    const onToggle = vi.fn()
    render(
      <MetricsPanel
        metrics={null} lifetimeStats={null} githubMetrics={githubMetrics}
        sessionCounts={{}} backgroundWorkers={[]} onToggleBgWorker={onToggle}
      />
    )
    // All workers default to enabled (On), so clicking toggles to disabled
    const onButtons = screen.getAllByText('On')
    fireEvent.click(onButtons[0]) // First worker = memory_sync
    expect(onToggle).toHaveBeenCalledWith('memory_sync', false)
  })

  it('shows Off button for disabled workers', () => {
    const bgWorkers = [
      { name: 'memory_sync', status: 'disabled', last_run: null, details: {} },
    ]
    render(
      <MetricsPanel
        metrics={null} lifetimeStats={null} githubMetrics={githubMetrics}
        sessionCounts={{}} backgroundWorkers={bgWorkers} onToggleBgWorker={() => {}}
      />
    )
    expect(screen.getByText('Off')).toBeInTheDocument()
    expect(screen.getByText('disabled')).toBeInTheDocument()
  })
})
