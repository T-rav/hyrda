import { describe, it, expect } from 'vitest'
import { reducer } from '../useHydraSocket'

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
  config: null,
  events: [],
  hitlItems: [],
  humanInputRequests: {},
  backgroundWorkers: [],
  metrics: null,
}

describe('useHydraSocket reducer', () => {
  it('initial state includes hitlItems and humanInputRequests', () => {
    expect(initialState.hitlItems).toEqual([])
    expect(initialState.humanInputRequests).toEqual({})
  })

  it('HITL_ITEMS action sets hitlItems', () => {
    const items = [
      { issue: 10, title: 'Bug', issueUrl: '', pr: 20, prUrl: '', branch: 'b1' },
    ]
    const next = reducer(initialState, { type: 'HITL_ITEMS', data: items })
    expect(next.hitlItems).toEqual(items)
  })

  it('HITL_ITEMS action replaces existing hitlItems', () => {
    const state = { ...initialState, hitlItems: [{ issue: 1 }] }
    const newItems = [{ issue: 2 }, { issue: 3 }]
    const next = reducer(state, { type: 'HITL_ITEMS', data: newItems })
    expect(next.hitlItems).toEqual(newItems)
  })

  it('HUMAN_INPUT_REQUESTS action sets humanInputRequests', () => {
    const requests = { '42': 'What approach?', '43': 'Please clarify' }
    const next = reducer(initialState, { type: 'HUMAN_INPUT_REQUESTS', data: requests })
    expect(next.humanInputRequests).toEqual(requests)
  })

  it('HUMAN_INPUT_SUBMITTED action removes entry from humanInputRequests', () => {
    const state = {
      ...initialState,
      humanInputRequests: { '42': 'What approach?', '43': 'Please clarify' },
    }
    const next = reducer(state, {
      type: 'HUMAN_INPUT_SUBMITTED',
      data: { issueNumber: '42' },
    })
    expect(next.humanInputRequests).toEqual({ '43': 'Please clarify' })
  })

  it('HUMAN_INPUT_SUBMITTED does not fail for missing key', () => {
    const state = {
      ...initialState,
      humanInputRequests: { '42': 'What approach?' },
    }
    const next = reducer(state, {
      type: 'HUMAN_INPUT_SUBMITTED',
      data: { issueNumber: '99' },
    })
    expect(next.humanInputRequests).toEqual({ '42': 'What approach?' })
  })

  it('phase_change resets hitlItems on new run', () => {
    const state = {
      ...initialState,
      phase: 'idle',
      hitlItems: [{ issue: 1 }],
    }
    const next = reducer(state, {
      type: 'phase_change',
      data: { phase: 'plan' },
      timestamp: new Date().toISOString(),
    })
    expect(next.hitlItems).toEqual([])
    expect(next.phase).toBe('plan')
  })

  it('phase_change does not reset hitlItems on non-new-run transitions', () => {
    const state = {
      ...initialState,
      phase: 'plan',
      hitlItems: [{ issue: 1 }],
    }
    const next = reducer(state, {
      type: 'phase_change',
      data: { phase: 'implement' },
      timestamp: new Date().toISOString(),
    })
    expect(next.hitlItems).toEqual([{ issue: 1 }])
    expect(next.phase).toBe('implement')
  })

  it('hitl_update event is added to events log', () => {
    const next = reducer(initialState, {
      type: 'hitl_update',
      data: { issue: 42, action: 'escalated' },
      timestamp: '2024-01-01T00:00:00Z',
    })
    expect(next.events).toHaveLength(1)
    expect(next.events[0].type).toBe('hitl_update')
    expect(next.events[0].data.issue).toBe(42)
  })

  describe('session counter tracking', () => {
    it('worker_update increments sessionImplemented when status transitions to done', () => {
      const state = {
        ...initialState,
        workers: { 10: { status: 'running', worker: 1, role: 'implementer', title: 'Issue #10', branch: '', transcript: [], pr: null } },
      }
      const next = reducer(state, {
        type: 'worker_update',
        data: { issue: 10, status: 'done', worker: 1, role: 'implementer' },
      })
      expect(next.sessionImplemented).toBe(1)
    })

    it('worker_update does not double-count if already done', () => {
      const state = {
        ...initialState,
        sessionImplemented: 1,
        workers: { 10: { status: 'done', worker: 1, role: 'implementer', title: 'Issue #10', branch: '', transcript: [], pr: null } },
      }
      const next = reducer(state, {
        type: 'worker_update',
        data: { issue: 10, status: 'done', worker: 1, role: 'implementer' },
      })
      expect(next.sessionImplemented).toBe(1)
    })

    it('worker_update does not increment sessionImplemented for non-done status', () => {
      const next = reducer(initialState, {
        type: 'worker_update',
        data: { issue: 10, status: 'running', worker: 1, role: 'implementer' },
      })
      expect(next.sessionImplemented).toBe(0)
    })

    it('triage_update increments sessionTriaged when status is done', () => {
      const next = reducer(initialState, {
        type: 'triage_update',
        data: { issue: 5, status: 'done', worker: 1 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.sessionTriaged).toBe(1)
    })

    it('triage_update does not double-count if already done', () => {
      const state = {
        ...initialState,
        sessionTriaged: 1,
        workers: { 'triage-5': { status: 'done', worker: 1, role: 'triage', title: 'Triage Issue #5', branch: '', transcript: [], pr: null } },
      }
      const next = reducer(state, {
        type: 'triage_update',
        data: { issue: 5, status: 'done', worker: 1 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.sessionTriaged).toBe(1)
    })

    it('triage_update does not increment sessionTriaged for running status', () => {
      const next = reducer(initialState, {
        type: 'triage_update',
        data: { issue: 5, status: 'running', worker: 1 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.sessionTriaged).toBe(0)
    })

    it('planner_update increments sessionPlanned when status is done', () => {
      const next = reducer(initialState, {
        type: 'planner_update',
        data: { issue: 7, status: 'done', worker: 2 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.sessionPlanned).toBe(1)
    })

    it('planner_update does not double-count if already done', () => {
      const state = {
        ...initialState,
        sessionPlanned: 1,
        workers: { 'plan-7': { status: 'done', worker: 2, role: 'planner', title: 'Plan Issue #7', branch: '', transcript: [], pr: null } },
      }
      const next = reducer(state, {
        type: 'planner_update',
        data: { issue: 7, status: 'done', worker: 2 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.sessionPlanned).toBe(1)
    })

    it('planner_update does not increment sessionPlanned for failed status', () => {
      const next = reducer(initialState, {
        type: 'planner_update',
        data: { issue: 7, status: 'failed', worker: 2 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.sessionPlanned).toBe(0)
    })

    it('planner_update passes through planning status instead of normalizing to running', () => {
      const next = reducer(initialState, {
        type: 'planner_update',
        data: { issue: 7, status: 'planning', worker: 2 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.workers['plan-7'].status).toBe('planning')
    })

    it('planner_update passes through non-terminal statuses as-is', () => {
      const next = reducer(initialState, {
        type: 'planner_update',
        data: { issue: 7, status: 'some_other', worker: 2 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.workers['plan-7'].status).toBe('some_other')
    })

    it('review_update increments sessionReviewed when status is done', () => {
      const next = reducer(initialState, {
        type: 'review_update',
        data: { issue: 3, pr: 20, status: 'done', worker: 3 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.sessionReviewed).toBe(1)
    })

    it('review_update does not double-count if already done', () => {
      const state = {
        ...initialState,
        sessionReviewed: 1,
        workers: { 'review-20': { status: 'done', worker: 3, role: 'reviewer', title: 'PR #20 (Issue #3)', branch: '', transcript: [], pr: 20 } },
      }
      const next = reducer(state, {
        type: 'review_update',
        data: { issue: 3, pr: 20, status: 'done', worker: 3 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.sessionReviewed).toBe(1)
    })

    it('review_update does not increment sessionReviewed for running status', () => {
      const next = reducer(initialState, {
        type: 'review_update',
        data: { issue: 3, pr: 20, status: 'running', worker: 3 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.sessionReviewed).toBe(0)
    })

    it('review_update passes through reviewing status instead of normalizing to running', () => {
      const next = reducer(initialState, {
        type: 'review_update',
        data: { issue: 3, pr: 20, status: 'reviewing', worker: 3 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.workers['review-20'].status).toBe('reviewing')
    })

    it('review_update passes through non-terminal statuses like fixing as-is', () => {
      const next = reducer(initialState, {
        type: 'review_update',
        data: { issue: 3, pr: 20, status: 'fixing', worker: 3 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.workers['review-20'].status).toBe('fixing')
    })

    it('phase_change resets all session counters on new run', () => {
      const state = {
        ...initialState,
        phase: 'idle',
        sessionTriaged: 3,
        sessionPlanned: 5,
        sessionImplemented: 4,
        sessionReviewed: 2,
        mergedCount: 1,
        sessionPrsCount: 4,
      }
      const next = reducer(state, {
        type: 'phase_change',
        data: { phase: 'plan' },
        timestamp: new Date().toISOString(),
      })
      expect(next.sessionTriaged).toBe(0)
      expect(next.sessionPlanned).toBe(0)
      expect(next.sessionImplemented).toBe(0)
      expect(next.sessionReviewed).toBe(0)
      expect(next.mergedCount).toBe(0)
      expect(next.sessionPrsCount).toBe(0)
    })

    it('phase_change does not reset session counters on non-new-run transitions', () => {
      const state = {
        ...initialState,
        phase: 'plan',
        sessionTriaged: 3,
        sessionPlanned: 5,
        sessionImplemented: 4,
        sessionReviewed: 2,
      }
      const next = reducer(state, {
        type: 'phase_change',
        data: { phase: 'implement' },
        timestamp: new Date().toISOString(),
      })
      expect(next.sessionTriaged).toBe(3)
      expect(next.sessionPlanned).toBe(5)
      expect(next.sessionImplemented).toBe(4)
      expect(next.sessionReviewed).toBe(2)
    })

    it('multiple stage completions accumulate independently', () => {
      let state = initialState
      state = reducer(state, {
        type: 'triage_update',
        data: { issue: 1, status: 'done', worker: 1 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      state = reducer(state, {
        type: 'triage_update',
        data: { issue: 2, status: 'done', worker: 1 },
        timestamp: '2024-01-01T00:00:01Z',
      })
      state = reducer(state, {
        type: 'planner_update',
        data: { issue: 1, status: 'done', worker: 2 },
        timestamp: '2024-01-01T00:00:02Z',
      })
      expect(state.sessionTriaged).toBe(2)
      expect(state.sessionPlanned).toBe(1)
      expect(state.sessionImplemented).toBe(0)
      expect(state.sessionReviewed).toBe(0)
    })
  })

  describe('background worker status', () => {
    it('initial state includes backgroundWorkers and metrics', () => {
      expect(initialState.backgroundWorkers).toEqual([])
      expect(initialState.metrics).toBeNull()
    })

    it('background_worker_status event updates backgroundWorkers array', () => {
      const next = reducer(initialState, {
        type: 'background_worker_status',
        data: { worker: 'memory_sync', status: 'ok', last_run: '2026-01-01T00:00:00Z', details: { count: 5 } },
        timestamp: '2026-01-01T00:00:00Z',
      })
      expect(next.backgroundWorkers).toHaveLength(1)
      expect(next.backgroundWorkers[0].name).toBe('memory_sync')
      expect(next.backgroundWorkers[0].status).toBe('ok')
    })

    it('background_worker_status event for existing worker replaces entry', () => {
      const state = {
        ...initialState,
        backgroundWorkers: [{ name: 'memory_sync', status: 'ok', last_run: '2026-01-01T00:00:00Z', details: {} }],
      }
      const next = reducer(state, {
        type: 'background_worker_status',
        data: { worker: 'memory_sync', status: 'error', last_run: '2026-01-01T00:01:00Z', details: {} },
        timestamp: '2026-01-01T00:01:00Z',
      })
      expect(next.backgroundWorkers).toHaveLength(1)
      expect(next.backgroundWorkers[0].status).toBe('error')
    })

    it('BACKGROUND_WORKERS action sets the full array', () => {
      const workers = [
        { name: 'memory_sync', status: 'ok', last_run: null, details: {} },
        { name: 'metrics', status: 'disabled', last_run: null, details: {} },
      ]
      const next = reducer(initialState, { type: 'BACKGROUND_WORKERS', data: workers })
      expect(next.backgroundWorkers).toEqual(workers)
    })

    it('METRICS action sets metrics state', () => {
      const metricsData = { lifetime: { issues_completed: 5, prs_merged: 3 }, rates: { merge_rate: 0.6 } }
      const next = reducer(initialState, { type: 'METRICS', data: metricsData })
      expect(next.metrics).toEqual(metricsData)
    })

    it('phase_change does NOT reset backgroundWorkers on new run', () => {
      const state = {
        ...initialState,
        phase: 'idle',
        backgroundWorkers: [{ name: 'memory_sync', status: 'ok' }],
        metrics: { lifetime: { issues_completed: 1 }, rates: {} },
      }
      const next = reducer(state, {
        type: 'phase_change',
        data: { phase: 'plan' },
        timestamp: new Date().toISOString(),
      })
      expect(next.backgroundWorkers).toEqual([{ name: 'memory_sync', status: 'ok' }])
      expect(next.metrics).toEqual({ lifetime: { issues_completed: 1 }, rates: {} })
    })
  })
})
