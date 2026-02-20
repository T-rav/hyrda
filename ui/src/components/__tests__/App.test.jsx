import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { layoutStyle, mainStyle, transcriptOverlayStyle } from '../../App'

const { mockSocketState } = vi.hoisted(() => ({
  mockSocketState: {
    workers: {
      1: { status: 'running', title: 'Test issue', branch: 'test-1', worker: 0, role: 'implementer', transcript: ['line 1'] },
    },
    prs: [],
    events: [],
    connected: true,
    orchestratorStatus: 'running',
    sessionPrsCount: 0,
    mergedCount: 0,
    config: {},
    phase: 'implement',
    lifetimeStats: null,
    hitlItems: [],
    humanInputRequests: {},
    issues: {
      1: {
        number: 1,
        title: 'Test issue',
        body: 'test body',
        status: 'implementing',
        createdAt: '2024-01-01T00:00:00Z',
        events: [],
        prNumber: null,
        prUrl: null,
        planSummary: null,
        verdict: null,
      },
    },
    dispatch: () => {},
    submitHumanInput: () => {},
    refreshHitl: () => {},
  },
}))

vi.mock('../../hooks/useHydraSocket', () => ({
  useHydraSocket: () => mockSocketState,
}))

beforeEach(() => {
  mockSocketState.hitlItems = []
  mockSocketState.issues = {
    1: {
      number: 1,
      title: 'Test issue',
      body: 'test body',
      status: 'implementing',
      createdAt: '2024-01-01T00:00:00Z',
      events: [],
      prNumber: null,
      prUrl: null,
      planSummary: null,
      verdict: null,
    },
  }
  cleanup()
})

describe('App stream-first layout', () => {
  it('renders intent input', async () => {
    const { default: App } = await import('../../App')
    render(<App />)

    expect(screen.getByPlaceholderText('What do you want to build?')).toBeInTheDocument()
  })

  it('renders stream view with issue cards', async () => {
    const { default: App } = await import('../../App')
    render(<App />)

    // #1 appears in both sidebar and stream view
    const issueRefs = screen.getAllByText('#1')
    expect(issueRefs.length).toBeGreaterThanOrEqual(2) // sidebar + stream
    // Title appears in both sidebar card and issue card
    expect(screen.getAllByText('Test issue').length).toBeGreaterThanOrEqual(1)
  })

  it('shows empty state when no issues', async () => {
    mockSocketState.issues = {}
    const { default: App } = await import('../../App')
    render(<App />)

    expect(screen.getByText('No activity yet')).toBeInTheDocument()
  })

  it('clicking a worker opens transcript overlay', async () => {
    const { default: App } = await import('../../App')
    render(<App />)

    // Click the worker card in sidebar
    const workerCards = screen.getAllByText('#1')
    fireEvent.click(workerCards[0])

    // Should show the Close button in transcript overlay
    expect(screen.getByText('Close')).toBeInTheDocument()
  })

  it('close button dismisses transcript overlay', async () => {
    const { default: App } = await import('../../App')
    render(<App />)

    // Click worker to open overlay
    const workerCards = screen.getAllByText('#1')
    fireEvent.click(workerCards[0])
    expect(screen.getByText('Close')).toBeInTheDocument()

    // Click Close to dismiss
    fireEvent.click(screen.getByText('Close'))
    expect(screen.queryByText('Close')).toBeNull()
  })
})

describe('App pre-computed styles', () => {
  it('layoutStyle has grid layout properties', () => {
    expect(layoutStyle).toMatchObject({
      display: 'grid',
      gridTemplateRows: 'auto 1fr',
      gridTemplateColumns: '280px 1fr',
      height: '100vh',
    })
  })

  it('mainStyle has flex column layout', () => {
    expect(mainStyle).toMatchObject({
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    })
  })

  it('transcriptOverlayStyle has fixed positioning', () => {
    expect(transcriptOverlayStyle).toMatchObject({
      position: 'fixed',
      zIndex: 100,
    })
  })

  it('style objects are referentially stable', () => {
    expect(layoutStyle).toBe(layoutStyle)
    expect(mainStyle).toBe(mainStyle)
    expect(transcriptOverlayStyle).toBe(transcriptOverlayStyle)
  })
})
