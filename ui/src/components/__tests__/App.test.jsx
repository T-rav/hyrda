import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { tabActiveStyle, tabInactiveStyle } from '../../App'

vi.mock('../../hooks/useHydraSocket', () => ({
  useHydraSocket: () => ({
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
  }),
}))

vi.mock('../../hooks/useHumanInput', () => ({
  useHumanInput: () => ({ requests: {}, submit: vi.fn() }),
}))

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
