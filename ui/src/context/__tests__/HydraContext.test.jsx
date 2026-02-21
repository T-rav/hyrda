import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { reducer } from '../HydraContext'

const emptyPipeline = {
  triage: [],
  plan: [],
  implement: [],
  review: [],
  hitl: [],
}

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
  pipelineIssues: { ...emptyPipeline },
  pipelinePollerLastRun: null,
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

describe('PIPELINE_SNAPSHOT reducer', () => {
  it('fully replaces pipelineIssues with server data', () => {
    const data = {
      triage: [{ issue_number: 1, title: 'Bug', url: '', status: 'queued' }],
      plan: [],
      implement: [{ issue_number: 2, title: 'Feature', url: '', status: 'active' }],
      review: [],
      hitl: [],
    }
    const next = reducer(initialState, { type: 'PIPELINE_SNAPSHOT', data })
    expect(next.pipelineIssues.triage).toHaveLength(1)
    expect(next.pipelineIssues.triage[0].issue_number).toBe(1)
    expect(next.pipelineIssues.implement).toHaveLength(1)
    expect(next.pipelineIssues.implement[0].status).toBe('active')
  })

  it('fills missing stages with empty arrays', () => {
    const data = { triage: [{ issue_number: 3, title: 'X', url: '', status: 'queued' }] }
    const next = reducer(initialState, { type: 'PIPELINE_SNAPSHOT', data })
    expect(next.pipelineIssues.triage).toHaveLength(1)
    expect(next.pipelineIssues.plan).toEqual([])
    expect(next.pipelineIssues.implement).toEqual([])
    expect(next.pipelineIssues.review).toEqual([])
    expect(next.pipelineIssues.hitl).toEqual([])
  })
})

describe('WS_PIPELINE_UPDATE reducer', () => {
  it('moves issue between stages on stage transition', () => {
    const state = {
      ...initialState,
      pipelineIssues: {
        ...emptyPipeline,
        triage: [{ issue_number: 5, title: 'Test', url: '', status: 'active' }],
      },
    }
    const next = reducer(state, {
      type: 'WS_PIPELINE_UPDATE',
      data: { issueNumber: 5, fromStage: 'triage', toStage: 'plan', status: 'queued' },
    })
    expect(next.pipelineIssues.triage).toHaveLength(0)
    expect(next.pipelineIssues.plan).toHaveLength(1)
    expect(next.pipelineIssues.plan[0].issue_number).toBe(5)
    expect(next.pipelineIssues.plan[0].status).toBe('queued')
  })

  it('updates status without moving when no fromStage', () => {
    const state = {
      ...initialState,
      pipelineIssues: {
        ...emptyPipeline,
        implement: [{ issue_number: 7, title: 'Impl', url: '', status: 'queued' }],
      },
    }
    const next = reducer(state, {
      type: 'WS_PIPELINE_UPDATE',
      data: { issueNumber: 7, fromStage: null, toStage: null, status: 'active' },
    })
    expect(next.pipelineIssues.implement).toHaveLength(1)
    expect(next.pipelineIssues.implement[0].status).toBe('active')
  })

  it('does not add unknown issues (no-op for missing issue)', () => {
    const next = reducer(initialState, {
      type: 'WS_PIPELINE_UPDATE',
      data: { issueNumber: 999, fromStage: 'triage', toStage: 'plan', status: 'queued' },
    })
    // Issue 999 not found in triage, should not appear in plan
    expect(next.pipelineIssues.plan).toHaveLength(0)
    expect(next.pipelineIssues.triage).toHaveLength(0)
  })
})

describe('TOGGLE_BG_WORKER reducer', () => {
  it('updates enabled flag on existing worker', () => {
    const state = {
      ...initialState,
      backgroundWorkers: [
        { name: 'triage', status: 'ok', enabled: true, last_run: null, details: {} },
      ],
    }
    const next = reducer(state, { type: 'TOGGLE_BG_WORKER', data: { name: 'triage', enabled: false } })
    expect(next.backgroundWorkers[0].enabled).toBe(false)
    expect(next.backgroundWorkers[0].status).toBe('ok')
  })

  it('creates stub entry for unknown worker', () => {
    const next = reducer(initialState, { type: 'TOGGLE_BG_WORKER', data: { name: 'plan', enabled: false } })
    expect(next.backgroundWorkers).toHaveLength(1)
    expect(next.backgroundWorkers[0].name).toBe('plan')
    expect(next.backgroundWorkers[0].enabled).toBe(false)
  })
})

describe('BACKGROUND_WORKERS preserves local overrides', () => {
  it('keeps local enabled flag when backend sends different value', () => {
    const state = {
      ...initialState,
      backgroundWorkers: [
        { name: 'triage', status: 'ok', enabled: false, last_run: null, details: {} },
      ],
    }
    const backendData = [
      { name: 'triage', status: 'ok', enabled: true, last_run: null, details: {} },
    ]
    const next = reducer(state, { type: 'BACKGROUND_WORKERS', data: backendData })
    // Local override (false) should win over backend (true)
    expect(next.backgroundWorkers[0].enabled).toBe(false)
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
