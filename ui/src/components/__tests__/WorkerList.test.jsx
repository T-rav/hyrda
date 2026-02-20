import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { WorkerList, cardStyle, cardActiveStyle, statusBadgeStyles } from '../WorkerList'

const statusColors = {
  queued:      { bg: 'rgba(139,148,158,0.15)', fg: '#8b949e' },
  running:     { bg: 'rgba(88,166,255,0.15)',  fg: '#58a6ff' },
  planning:    { bg: 'rgba(163,113,247,0.15)', fg: '#a371f7' },
  testing:     { bg: 'rgba(210,153,34,0.15)',  fg: '#d29922' },
  committing:  { bg: 'rgba(210,134,22,0.15)',  fg: '#d18616' },
  quality_fix: { bg: 'rgba(210,153,34,0.15)',  fg: '#d29922' },
  merge_fix:   { bg: 'rgba(227,134,38,0.15)',  fg: '#e3862a' },
  done:        { bg: 'rgba(63,185,80,0.15)',   fg: '#3fb950' },
  failed:      { bg: 'rgba(248,81,73,0.15)',   fg: '#f85149' },
}

describe('WorkerList pre-computed styles', () => {
  it('cardActiveStyle includes properties from both card and active', () => {
    // card props
    expect(cardActiveStyle).toHaveProperty('padding')
    expect(cardActiveStyle).toHaveProperty('cursor', 'pointer')
    // active props
    expect(cardActiveStyle).toHaveProperty('background', 'rgba(88,166,255,0.08)')
    expect(cardActiveStyle.borderLeft).toBe('3px solid #58a6ff')
  })

  it('cardStyle does not have active background', () => {
    expect(cardStyle.background).toBeUndefined()
    expect(cardStyle.borderLeft).toBe('3px solid #484f58')
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
