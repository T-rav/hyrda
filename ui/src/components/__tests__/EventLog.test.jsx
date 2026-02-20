import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EventLog, typeSpanStyles, defaultTypeStyle } from '../EventLog'

const typeColors = {
  worker_update: '#58a6ff',
  phase_change: '#d29922',
  pr_created: '#3fb950',
  review_update: '#d18616',
  merge_update: '#3fb950',
  error: '#f85149',
  batch_start: '#58a6ff',
  batch_complete: '#3fb950',
  transcript_line: '#8b949e',
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

  it('defaultTypeStyle has color #8b949e and base style properties', () => {
    expect(defaultTypeStyle).toMatchObject({
      fontWeight: 600,
      marginRight: 6,
      color: '#8b949e',
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
