import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { reducer } from '../HydraContext'

const initialState = {
  connected: false,
  batchNum: 0,
  phase: 'idle',
  orchestratorStatus: 'idle',
  workers: {},
  prs: [],
  reviews: [],
  mergedCount: 0,
  sessionPrsCount: 0,
  sessionTriaged: 0,
  sessionPlanned: 0,
  sessionImplemented: 0,
  sessionReviewed: 0,
  lifetimeStats: null,
  queueStats: null,
  config: null,
  events: [],
  hitlItems: [],
  hitlEscalation: null,
  humanInputRequests: {},
  backgroundWorkers: [],
  metrics: null,
  systemAlert: null,
  intents: [],
  githubMetrics: null,
}

describe('HydraContext reducer', () => {
  it('GITHUB_METRICS action sets githubMetrics state', () => {
    const data = {
      open_by_label: { 'hydra-plan': 3, 'hydra-ready': 1 },
      total_closed: 10,
      total_merged: 8,
    }
    const next = reducer(initialState, { type: 'GITHUB_METRICS', data })
    expect(next.githubMetrics).toEqual(data)
  })

  it('GITHUB_METRICS replaces existing data', () => {
    const state = {
      ...initialState,
      githubMetrics: { open_by_label: {}, total_closed: 0, total_merged: 0 },
    }
    const data = {
      open_by_label: { 'hydra-plan': 5 },
      total_closed: 15,
      total_merged: 12,
    }
    const next = reducer(state, { type: 'GITHUB_METRICS', data })
    expect(next.githubMetrics).toEqual(data)
  })

  it('orchestrator_status clears session state but not githubMetrics', () => {
    const state = {
      ...initialState,
      orchestratorStatus: 'running',
      sessionTriaged: 3,
      sessionPlanned: 2,
      githubMetrics: { open_by_label: {}, total_closed: 5, total_merged: 3 },
    }
    const next = reducer(state, {
      type: 'orchestrator_status',
      data: { status: 'idle' },
      timestamp: new Date().toISOString(),
    })
    expect(next.sessionTriaged).toBe(0)
    expect(next.sessionPlanned).toBe(0)
    expect(next.githubMetrics).toEqual({ open_by_label: {}, total_closed: 5, total_merged: 3 })
  })

  it('phase_change clears session state but not githubMetrics on new run', () => {
    const state = {
      ...initialState,
      phase: 'idle',
      sessionTriaged: 3,
      githubMetrics: { open_by_label: { 'hydra-plan': 2 }, total_closed: 1, total_merged: 1 },
    }
    const next = reducer(state, {
      type: 'phase_change',
      data: { phase: 'plan' },
      timestamp: new Date().toISOString(),
    })
    expect(next.sessionTriaged).toBe(0)
    expect(next.githubMetrics).toEqual({ open_by_label: { 'hydra-plan': 2 }, total_closed: 1, total_merged: 1 })
  })
})

describe('HydraProvider', () => {
  it('renders children', async () => {
    // Dynamic import to avoid WebSocket connection in test
    const { HydraProvider } = await import('../HydraContext')

    // We can't fully test the provider without mocking WebSocket,
    // but we can verify it renders children
    // Note: The provider will attempt to connect but the test env has no server
    render(
      <HydraProvider>
        <div>Test Child</div>
      </HydraProvider>
    )
    expect(screen.getByText('Test Child')).toBeInTheDocument()
  })
})
