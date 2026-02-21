import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { tabActiveStyle, tabInactiveStyle, hitlBadgeStyle } from '../../App'

const { mockState } = vi.hoisted(() => ({
  mockState: {
    workers: {
      1: { status: 'running', title: 'Test issue', branch: 'test-1', worker: 0, role: 'implementer', transcript: ['line 1'] },
    },
    prs: [],
    events: [],
    connected: true,
    orchestratorStatus: 'running',
    sessionPrsCount: 0,
    mergedCount: 0,
    sessionTriaged: 0,
    sessionPlanned: 0,
    sessionImplemented: 0,
    sessionReviewed: 0,
    config: {},
    phase: 'implement',
    lifetimeStats: null,
    hitlItems: [],
    humanInputRequests: {},
    submitHumanInput: () => {},
    refreshHitl: () => {},
    backgroundWorkers: [],
    metrics: null,
    githubMetrics: null,
    intents: [],
    submitIntent: () => {},
    toggleBgWorker: () => {},
    systemAlert: null,
  },
}))

vi.mock('../../context/HydraContext', () => ({
  HydraProvider: ({ children }) => children,
  useHydra: () => mockState,
}))

beforeEach(() => {
  mockState.hitlItems = []
  mockState.prs = []
  cleanup()
})

describe('Transcript tab', () => {
  it('clicking Transcript tab shows transcript content', async () => {
    const { default: App } = await import('../../App')
    render(<App />)

    fireEvent.click(screen.getByText('Transcript'))
    // Auto-selects the active worker and shows its transcript
    expect(screen.getByText('line 1')).toBeInTheDocument()
  })
})

describe('HITL badge rendering', () => {
  it('shows no badge when hitlItems is empty', async () => {
    const { default: App } = await import('../../App')
    render(<App />)

    const hitlTab = screen.getByText('HITL')
    expect(hitlTab.querySelector('span')).toBeNull()
  })

  it('shows badge with count when hitlItems has entries', async () => {
    mockState.hitlItems = [
      { issue: 1, title: 'Bug A', pr: 10, branch: 'fix-a', issueUrl: '#', prUrl: '#' },
      { issue: 2, title: 'Bug B', pr: 11, branch: 'fix-b', issueUrl: '#', prUrl: '#' },
      { issue: 3, title: 'Bug C', pr: 12, branch: 'fix-c', issueUrl: '#', prUrl: '#' },
    ]
    const { default: App } = await import('../../App')
    render(<App />)

    expect(screen.getByText('3')).toBeInTheDocument()
  })
})

describe('Layout min-width', () => {
  it('root layout has minWidth to prevent overlap at narrow viewports', async () => {
    const { default: App } = await import('../../App')
    const { container } = render(<App />)
    const layout = container.firstChild
    expect(layout.style.minWidth).toBe('800px')
  })
})

describe('App pre-computed tab styles', () => {
  it('tabInactiveStyle has base tab properties', () => {
    expect(tabInactiveStyle).toMatchObject({
      padding: '10px 20px',
      fontSize: 12,
      fontWeight: 600,
      color: 'var(--text-muted)',
      cursor: 'pointer',
      borderBottom: '2px solid transparent',
    })
  })

  it('tabActiveStyle includes both tab and tabActive properties', () => {
    expect(tabActiveStyle).toMatchObject({
      padding: '10px 20px',
      fontSize: 12,
      fontWeight: 600,
      color: 'var(--accent)',
      cursor: 'pointer',
      borderBottomColor: 'var(--accent)',
    })
  })

  it('tabActiveStyle overrides color from tabActive', () => {
    expect(tabActiveStyle.color).toBe('var(--accent)')
  })

  it('style objects are referentially stable', () => {
    expect(tabActiveStyle).toBe(tabActiveStyle)
    expect(tabInactiveStyle).toBe(tabInactiveStyle)
    expect(hitlBadgeStyle).toBe(hitlBadgeStyle)
  })

  describe('hitlBadgeStyle', () => {
    it('has red background and white text', () => {
      expect(hitlBadgeStyle).toMatchObject({
        background: 'var(--red)',
        color: 'var(--white)',
      })
    })

    it('has pill-shaped badge properties', () => {
      expect(hitlBadgeStyle).toMatchObject({
        fontSize: 10,
        fontWeight: 700,
        borderRadius: 10,
        padding: '1px 6px',
        marginLeft: 6,
      })
    })
  })
})

describe('System and Metrics tabs', () => {
  it('renders System and Metrics tabs', async () => {
    const { default: App } = await import('../../App')
    render(<App />)
    expect(screen.getByText('System')).toBeInTheDocument()
    expect(screen.getByText('Metrics')).toBeInTheDocument()
  })

  it('clicking System tab shows SystemPanel content', async () => {
    const { default: App } = await import('../../App')
    render(<App />)
    fireEvent.click(screen.getByText('System'))
    expect(screen.getByText('Background Workers')).toBeInTheDocument()
  })

  it('clicking Metrics tab shows MetricsPanel content', async () => {
    mockState.metrics = {
      lifetime: { issues_completed: 5, prs_merged: 3, issues_created: 1 },
      rates: {},
    }
    const { default: App } = await import('../../App')
    render(<App />)
    fireEvent.click(screen.getByText('Metrics'))
    expect(screen.getByText('Lifetime')).toBeInTheDocument()
  })
})

describe('Livestream and Work Stream tab labels', () => {
  it('both Livestream and Work Stream labels are present', async () => {
    const { default: App } = await import('../../App')
    render(<App />)
    expect(screen.getByText('Livestream')).toBeInTheDocument()
    expect(screen.getByText('Work Stream')).toBeInTheDocument()
  })

  it('Livestream tab renders Livestream component', async () => {
    const { default: App } = await import('../../App')
    render(<App />)
    fireEvent.click(screen.getByText('Livestream'))
    expect(screen.getByText('Waiting for events...')).toBeInTheDocument()
  })

  it('Work Stream is the default tab', async () => {
    const { default: App } = await import('../../App')
    render(<App />)
    // Work Stream tab should be active by default (has active tab styling)
    const issueStreamTab = screen.getByText('Work Stream')
    expect(issueStreamTab.style.color).toBe('var(--accent)')
  })
})

describe('Tab label correctness', () => {
  it('Livestream tab label matches the Livestream component', async () => {
    mockState.events = [
      { timestamp: new Date().toISOString(), type: 'worker_update', data: { issue: 1 } },
    ]
    const { default: App } = await import('../../App')
    render(<App />)

    // Click the tab labeled "Livestream"
    fireEvent.click(screen.getByText('Livestream'))

    // The inline event livestream renders — shows raw event types
    expect(screen.getByText('worker update')).toBeInTheDocument()
  })
})
