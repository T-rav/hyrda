import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { WorkerList, cardStyle, cardActiveStyle, statusBadgeStyles } from '../WorkerList'

const statusColors = {
  queued:      { bg: 'var(--muted-subtle)',  fg: 'var(--text-muted)' },
  running:     { bg: 'var(--accent-subtle)', fg: 'var(--accent)' },
  planning:    { bg: 'var(--purple-subtle)', fg: 'var(--purple)' },
  testing:     { bg: 'var(--yellow-subtle)', fg: 'var(--yellow)' },
  committing:  { bg: 'var(--orange-subtle)', fg: 'var(--orange)' },
  quality_fix: { bg: 'var(--yellow-subtle)', fg: 'var(--yellow)' },
  merge_fix:   { bg: 'var(--orange-subtle)', fg: 'var(--orange)' },
  reviewing:   { bg: 'var(--orange-subtle)', fg: 'var(--orange)' },
  done:        { bg: 'var(--green-subtle)',  fg: 'var(--green)' },
  failed:      { bg: 'var(--red-subtle)',    fg: 'var(--red)' },
}

describe('WorkerList pre-computed styles', () => {
  it('cardActiveStyle includes properties from both card and active', () => {
    // card props
    expect(cardActiveStyle).toHaveProperty('padding')
    expect(cardActiveStyle).toHaveProperty('cursor', 'pointer')
    // active props
    expect(cardActiveStyle).toHaveProperty('background', 'var(--accent-hover)')
    expect(cardActiveStyle.borderLeft).toBe('3px solid var(--accent)')
  })

  it('cardStyle does not have active background', () => {
    expect(cardStyle.background).toBeUndefined()
    expect(cardStyle.borderLeft).toBe('3px solid var(--text-inactive)')
  })

  it('statusBadgeStyles has an entry for every statusColors key', () => {
    for (const key of Object.keys(statusColors)) {
      expect(statusBadgeStyles).toHaveProperty(key)
    }
  })

  it('each statusBadgeStyle includes base status style and correct bg/fg', () => {
    for (const [key, { bg, fg }] of Object.entries(statusColors)) {
      expect(statusBadgeStyles[key]).toMatchObject({
        fontSize: 11,
        padding: '2px 8px',
        borderRadius: 8,
        fontWeight: 600,
        background: bg,
        color: fg,
      })
    }
  })

  it('style objects are referentially stable', () => {
    expect(statusBadgeStyles.running).toBe(statusBadgeStyles.running)
    expect(cardActiveStyle).toBe(cardActiveStyle)
  })
})

describe('WorkerList component', () => {
  it('renders without errors with empty workers', () => {
    render(<WorkerList workers={{}} selectedWorker={null} onSelect={() => {}} />)
    // Section headers should still render
    expect(screen.getByText('Triage')).toBeInTheDocument()
    expect(screen.getByText('Planners')).toBeInTheDocument()
    expect(screen.getByText('Implementers')).toBeInTheDocument()
    expect(screen.getByText('Reviewers')).toBeInTheDocument()
  })

  it('renders workers with reviewing and planning statuses', () => {
    const workers = {
      'review-1': { status: 'reviewing', title: 'Review PR', branch: 'feat', worker: 0, role: 'reviewer' },
      3: { status: 'planning', title: 'Plan issue', branch: '', worker: 1, role: 'planner' },
    }
    render(<WorkerList workers={workers} selectedWorker={null} onSelect={() => {}} />)
    expect(screen.getByText('reviewing')).toBeInTheDocument()
    expect(screen.getByText('planning')).toBeInTheDocument()
  })

  it('renders workers with pre-computed styles', () => {
    const workers = {
      1: { status: 'running', title: 'Test issue', branch: 'test-branch', worker: 0, role: 'implementer' },
      2: { status: 'done', title: 'Done issue', branch: 'done-branch', worker: 1, role: 'implementer' },
    }
    render(<WorkerList workers={workers} selectedWorker={1} onSelect={() => {}} />)
    expect(screen.getByText('#1')).toBeInTheDocument()
    expect(screen.getByText('#2')).toBeInTheDocument()
    expect(screen.getByText('running')).toBeInTheDocument()
    expect(screen.getByText('done')).toBeInTheDocument()
  })
})
