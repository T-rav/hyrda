import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SystemPanel } from '../SystemPanel'

const mockWorkers = [
  { name: 'memory_sync', status: 'ok', last_run: new Date().toISOString(), details: { item_count: 12, digest_chars: 2400 } },
  { name: 'retrospective', status: 'error', last_run: '2026-02-20T10:28:00Z', details: { last_issue: 42 } },
  { name: 'metrics', status: 'ok', last_run: '2026-02-20T10:25:00Z', details: {} },
  { name: 'review_insights', status: 'disabled', last_run: null, details: {} },
]

describe('SystemPanel', () => {
  it('renders all 4 worker cards', () => {
    render(<SystemPanel backgroundWorkers={mockWorkers} />)
    expect(screen.getByText('Memory Sync')).toBeInTheDocument()
    expect(screen.getByText('Retrospective')).toBeInTheDocument()
    expect(screen.getByText('Metrics')).toBeInTheDocument()
    expect(screen.getByText('Review Insights')).toBeInTheDocument()
  })

  it('shows correct status dot color for ok workers', () => {
    render(<SystemPanel backgroundWorkers={mockWorkers} />)
    const dot = screen.getByTestId('dot-memory_sync')
    expect(dot.style.background).toBe('var(--green)')
  })

  it('shows correct status dot color for error workers', () => {
    render(<SystemPanel backgroundWorkers={mockWorkers} />)
    const dot = screen.getByTestId('dot-retrospective')
    expect(dot.style.background).toBe('var(--red)')
  })

  it('shows correct status dot color for disabled workers', () => {
    render(<SystemPanel backgroundWorkers={mockWorkers} />)
    const dot = screen.getByTestId('dot-review_insights')
    expect(dot.style.background).toBe('var(--text-inactive)')
  })

  it('shows disabled state when worker has not reported', () => {
    render(<SystemPanel backgroundWorkers={[]} />)
    // All workers should appear from BACKGROUND_WORKERS constant
    expect(screen.getByText('Memory Sync')).toBeInTheDocument()
    // All should show disabled status
    const dots = [
      screen.getByTestId('dot-memory_sync'),
      screen.getByTestId('dot-retrospective'),
      screen.getByTestId('dot-metrics'),
      screen.getByTestId('dot-review_insights'),
    ]
    dots.forEach(dot => {
      expect(dot.style.background).toBe('var(--text-inactive)')
    })
  })

  it('shows last run time when available', () => {
    render(<SystemPanel backgroundWorkers={mockWorkers} />)
    // Memory sync was just now, so should show "just now"
    expect(screen.getAllByText(/Last run:/).length).toBe(4)
  })

  it('shows "never" for workers that have not run', () => {
    render(<SystemPanel backgroundWorkers={[]} />)
    const neverTexts = screen.getAllByText(/never/)
    expect(neverTexts.length).toBe(4)
  })

  it('shows detail key-value pairs', () => {
    render(<SystemPanel backgroundWorkers={mockWorkers} />)
    expect(screen.getByText('item count')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('digest chars')).toBeInTheDocument()
    expect(screen.getByText('2400')).toBeInTheDocument()
  })
})
