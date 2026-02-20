import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { tabActiveStyle, tabInactiveStyle, tabBadgeStyle } from '../../App'

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

// Mock hooks to control state for render tests
vi.mock('../../hooks/useHydraSocket', () => ({
  useHydraSocket: vi.fn(),
}))

vi.mock('../../hooks/useHumanInput', () => ({
  useHumanInput: () => ({ requests: {}, submit: vi.fn() }),
}))

import { useHydraSocket } from '../../hooks/useHydraSocket'
import App from '../../App'

function makeState(overrides = {}) {
  return {
    connected: false,
    phase: 'idle',
    orchestratorStatus: 'idle',
    workers: {},
    prs: [],
    reviews: [],
    mergedCount: 0,
    sessionPrsCount: 0,
    lifetimeStats: null,
    config: null,
    events: [],
    ...overrides,
  }
}

function getPrTab() {
  return screen.getByText('Pull Requests').closest('div')
}

describe('PR tab badge rendering', () => {
  it('shows Pull Requests label without badge when no PRs exist', () => {
    useHydraSocket.mockReturnValue(makeState({ prs: [] }))
    render(<App />)
    const tab = getPrTab()
    expect(tab).toBeInTheDocument()
    expect(within(tab).queryByText(/\d+/)).not.toBeInTheDocument()
  })

  it('shows badge with count when PRs exist', () => {
    const prs = [
      { pr: 1, title: 'PR 1' },
      { pr: 2, title: 'PR 2' },
      { pr: 3, title: 'PR 3' },
    ]
    useHydraSocket.mockReturnValue(makeState({ prs }))
    render(<App />)
    const tab = getPrTab()
    expect(within(tab).getByText('3')).toBeInTheDocument()
  })

  it('updates badge count when PR list changes', () => {
    const prs = [{ pr: 1, title: 'PR 1' }]
    useHydraSocket.mockReturnValue(makeState({ prs }))
    const { rerender } = render(<App />)
    const tab = getPrTab()
    expect(within(tab).getByText('1')).toBeInTheDocument()

    const morePrs = [...prs, { pr: 2, title: 'PR 2' }, { pr: 3, title: 'PR 3' }, { pr: 4, title: 'PR 4' }, { pr: 5, title: 'PR 5' }]
    useHydraSocket.mockReturnValue(makeState({ prs: morePrs }))
    rerender(<App />)
    expect(within(getPrTab()).getByText('5')).toBeInTheDocument()
  })
})
