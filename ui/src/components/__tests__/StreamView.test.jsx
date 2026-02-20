import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { StreamView, streamStyles } from '../StreamView'

beforeEach(() => cleanup())

const makeIssue = (number, overrides = {}) => ({
  number,
  title: `Issue ${number}`,
  body: `Body of issue ${number}`,
  status: 'implementing',
  createdAt: '2024-01-01T00:00:00Z',
  events: [],
  prNumber: null,
  prUrl: null,
  planSummary: null,
  verdict: null,
  ...overrides,
})

describe('StreamView', () => {
  it('renders empty state when no issues', () => {
    render(<StreamView issues={{}} />)
    expect(screen.getByText('No activity yet')).toBeInTheDocument()
    expect(screen.getByText(/Type something above/)).toBeInTheDocument()
  })

  it('renders issue cards for each issue', () => {
    const issues = {
      1: makeIssue(1, { title: 'First issue' }),
      2: makeIssue(2, { title: 'Second issue' }),
    }
    render(<StreamView issues={issues} />)

    expect(screen.getByText('#1')).toBeInTheDocument()
    expect(screen.getByText('First issue')).toBeInTheDocument()
    expect(screen.getByText('#2')).toBeInTheDocument()
    expect(screen.getByText('Second issue')).toBeInTheDocument()
  })

  it('active issues appear before completed ones', () => {
    const issues = {
      1: makeIssue(1, { title: 'Merged issue', status: 'merged' }),
      2: makeIssue(2, { title: 'Active issue', status: 'implementing' }),
    }
    const { container } = render(<StreamView issues={issues} />)

    const articles = container.querySelectorAll('[role="article"]')
    expect(articles).toHaveLength(2)
    // Active (implementing) should come first
    expect(articles[0].textContent).toContain('#2')
    expect(articles[1].textContent).toContain('#1')
  })

  it('sorts by status priority: implementing > reviewing > planning', () => {
    const issues = {
      1: makeIssue(1, { status: 'planning' }),
      2: makeIssue(2, { status: 'implementing' }),
      3: makeIssue(3, { status: 'reviewing' }),
    }
    const { container } = render(<StreamView issues={issues} />)

    const articles = container.querySelectorAll('[role="article"]')
    expect(articles[0].textContent).toContain('#2') // implementing
    expect(articles[1].textContent).toContain('#3') // reviewing
    expect(articles[2].textContent).toContain('#1') // planning
  })
})

describe('StreamView pre-computed styles', () => {
  it('container has flex layout', () => {
    expect(streamStyles.container).toMatchObject({
      flex: 1,
      overflowY: 'auto',
    })
  })

  it('empty state is centered', () => {
    expect(streamStyles.empty).toMatchObject({
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    })
  })

  it('style objects are referentially stable', () => {
    expect(streamStyles.container).toBe(streamStyles.container)
    expect(streamStyles.empty).toBe(streamStyles.empty)
  })
})
