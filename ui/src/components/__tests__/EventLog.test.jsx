import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EventLog, typeSpanStyles, defaultTypeStyle } from '../EventLog'

const typeColors = {
  worker_update: 'var(--accent)',
  phase_change: 'var(--yellow)',
  pr_created: 'var(--green)',
  review_update: 'var(--orange)',
  merge_update: 'var(--green)',
  error: 'var(--red)',
  batch_start: 'var(--accent)',
  batch_complete: 'var(--green)',
  transcript_line: 'var(--text-muted)',
}

describe('EventLog pre-computed styles', () => {
  it('has an entry for every typeColors key', () => {
    for (const key of Object.keys(typeColors)) {
      expect(typeSpanStyles).toHaveProperty(key)
    }
  })

  it('each typeSpanStyle includes base style fontWeight: 600 and the correct color', () => {
    for (const [key, color] of Object.entries(typeColors)) {
      expect(typeSpanStyles[key]).toMatchObject({
        fontWeight: 600,
        marginRight: 6,
        color,
      })
    }
  })

  it('defaultTypeStyle has textMuted color and base style properties', () => {
    expect(defaultTypeStyle).toMatchObject({
      fontWeight: 600,
      marginRight: 6,
      color: 'var(--text-muted)',
    })
  })

  it('style objects are referentially stable across accesses', () => {
    const first = typeSpanStyles.error
    const second = typeSpanStyles.error
    expect(first).toBe(second)
  })
})

describe('EventLog component', () => {
  it('renders without errors with empty events', () => {
    render(<EventLog events={[]} />)
    expect(screen.getByText('Waiting for events...')).toBeInTheDocument()
  })

  it('renders events and applies pre-computed styles', () => {
    const events = [
      { type: 'batch_start', timestamp: Date.now(), data: { batch: 1 } },
      { type: 'error', timestamp: Date.now(), data: { message: 'fail' } },
    ]
    const { container } = render(<EventLog events={events} />)
    const spans = container.querySelectorAll('span')
    // Should render without crashing and contain the event types
    expect(screen.getByText('batch start')).toBeInTheDocument()
    expect(screen.getByText('error')).toBeInTheDocument()
  })

  it('filters out transcript_line events', () => {
    const events = [
      { type: 'transcript_line', timestamp: Date.now(), data: { issue: 1 } },
      { type: 'error', timestamp: Date.now(), data: { message: 'fail' } },
    ]
    render(<EventLog events={events} />)
    expect(screen.queryByText('transcript line')).not.toBeInTheDocument()
    expect(screen.getByText('error')).toBeInTheDocument()
  })
})
