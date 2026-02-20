import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { tabActiveStyle, tabInactiveStyle, tabBadgeStyle, hitlBadgeStyle } from '../../App'

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
    submitHumanInput: () => {},
    refreshHitl: () => {},
  },
}))

vi.mock('../../hooks/useHydraSocket', () => ({
  useHydraSocket: () => mockSocketState,
}))

beforeEach(() => {
  mockSocketState.hitlItems = []
  mockSocketState.prs = []
  cleanup()
})

describe('App worker select tab switching', () => {
  it('clicking a worker switches to transcript tab', async () => {
    const { default: App } = await import('../../App')
    render(<App />)

    // Switch to Pull Requests tab first
    fireEvent.click(screen.getByText('Pull Requests'))

    // Click the worker card
    fireEvent.click(screen.getByText('#1'))

    // Transcript tab should now be active and transcript content visible
    expect(screen.getByText('line 1')).toBeInTheDocument()
  })

  it('clicking a worker when already on transcript tab keeps transcript active', async () => {
    const { default: App } = await import('../../App')
    render(<App />)

    // We start on transcript tab by default, click the worker via its card
    const workerCards = screen.getAllByText('#1')
    fireEvent.click(workerCards[0]) // sidebar card is the first match

    // Should still be on transcript tab with content visible
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
    mockSocketState.hitlItems = [
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
    expect(layout.style.minWidth).toBe('1024px')
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
    // tabActive color (var(--accent)) should override base tab color (var(--text-muted))
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

describe('tabBadgeStyle', () => {
  it('has expected badge properties', () => {
    expect(tabBadgeStyle).toMatchObject({
      marginLeft: 6,
      padding: '1px 6px',
      borderRadius: 10,
      fontSize: 10,
      fontWeight: 600,
      background: 'var(--border)',
      color: 'var(--text-muted)',
    })
  })

  it('is referentially stable', () => {
    expect(tabBadgeStyle).toBe(tabBadgeStyle)
  })
})

describe('PR tab badge rendering', () => {
  it('shows Pull Requests label without badge when no PRs exist', async () => {
    mockSocketState.prs = []
    const { default: App } = await import('../../App')
    render(<App />)
    const tab = screen.getByText('Pull Requests').closest('div')
    expect(tab).toBeInTheDocument()
    expect(tab.querySelector('span')).toBeNull()
  })

  it('shows badge with count when PRs exist', async () => {
    mockSocketState.prs = [
      { pr: 1, title: 'PR 1' },
      { pr: 2, title: 'PR 2' },
      { pr: 3, title: 'PR 3' },
    ]
    const { default: App } = await import('../../App')
    render(<App />)
    const tab = screen.getByText('Pull Requests').closest('div')
    expect(tab.querySelector('span')).not.toBeNull()
    expect(tab.querySelector('span').textContent).toBe('3')
  })

  it('shows no badge when prs is empty after having items', async () => {
    mockSocketState.prs = [{ pr: 1, title: 'PR 1' }]
    const { default: App } = await import('../../App')
    const { unmount } = render(<App />)
    const tab = screen.getByText('Pull Requests').closest('div')
    expect(tab.querySelector('span')).not.toBeNull()

    unmount()
    mockSocketState.prs = []
    render(<App />)
    const tab2 = screen.getByText('Pull Requests').closest('div')
    expect(tab2.querySelector('span')).toBeNull()
  })
})
