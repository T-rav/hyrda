import { describe, it, expect } from 'vitest'
import { reducer } from '../useHydraSocket'
import { MAX_EVENTS } from '../../constants'

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

  describe('event cap (MAX_EVENTS)', () => {
    it('addEvent caps events at MAX_EVENTS', () => {
      const state = {
        ...initialState,
        events: Array.from({ length: MAX_EVENTS }, (_, i) => ({
          type: 'worker_update',
          timestamp: `2024-01-01T00:00:${String(i).padStart(6, '0')}Z`,
          data: {},
        })),
      }
      const next = reducer(state, {
        type: 'error',
        data: { message: 'overflow' },
        timestamp: '2024-01-02T00:00:00Z',
      })
      expect(next.events).toHaveLength(MAX_EVENTS)
      expect(next.events[0].type).toBe('error')
    })

    it('addEvent does not truncate below MAX_EVENTS', () => {
      const state = { ...initialState, events: [] }
      const next = reducer(state, {
        type: 'error',
        data: { message: 'test' },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.events).toHaveLength(1)
    })
  })

  describe('BACKFILL_EVENTS', () => {
    it('merges new events without duplicating existing', () => {
      const existing = [
        { type: 'batch_start', timestamp: '2024-01-01T00:00:02Z', data: { batch: 2 } },
        { type: 'batch_start', timestamp: '2024-01-01T00:00:01Z', data: { batch: 1 } },
      ]
      const state = { ...initialState, events: existing }
      const backfill = [
        { type: 'batch_start', timestamp: '2024-01-01T00:00:01Z', data: { batch: 1 } },
        { type: 'phase_change', timestamp: '2024-01-01T00:00:00Z', data: { phase: 'plan' } },
      ]
      const next = reducer(state, { type: 'BACKFILL_EVENTS', data: backfill })
      expect(next.events).toHaveLength(3)
      expect(next.events[0].timestamp).toBe('2024-01-01T00:00:02Z')
      expect(next.events[2].timestamp).toBe('2024-01-01T00:00:00Z')
    })

    it('populates empty state', () => {
      const backfill = [
        { type: 'batch_start', timestamp: '2024-01-01T00:00:01Z', data: { batch: 1 } },
      ]
      const next = reducer(initialState, { type: 'BACKFILL_EVENTS', data: backfill })
      expect(next.events).toHaveLength(1)
      expect(next.events[0].type).toBe('batch_start')
    })

    it('with empty data is a no-op', () => {
      const state = {
        ...initialState,
        events: [
          { type: 'batch_start', timestamp: '2024-01-01T00:00:01Z', data: {} },
        ],
      }
      const next = reducer(state, { type: 'BACKFILL_EVENTS', data: [] })
      expect(next.events).toHaveLength(1)
    })

    it('caps combined events at MAX_EVENTS', () => {
      const existing = Array.from({ length: 3000 }, (_, i) => ({
        type: 'worker_update',
        timestamp: `2024-01-01T01:00:${String(i).padStart(6, '0')}Z`,
        data: {},
      }))
      const backfill = Array.from({ length: 3000 }, (_, i) => ({
        type: 'phase_change',
        timestamp: `2024-01-01T00:00:${String(i).padStart(6, '0')}Z`,
        data: {},
      }))
      const state = { ...initialState, events: existing }
      const next = reducer(state, { type: 'BACKFILL_EVENTS', data: backfill })
      expect(next.events).toHaveLength(MAX_EVENTS)
    })

    it('sorts merged events newest-first', () => {
      const existing = [
        { type: 'batch_start', timestamp: '2024-01-01T00:00:03Z', data: {} },
        { type: 'batch_start', timestamp: '2024-01-01T00:00:01Z', data: {} },
      ]
      const backfill = [
        { type: 'phase_change', timestamp: '2024-01-01T00:00:04Z', data: {} },
        { type: 'phase_change', timestamp: '2024-01-01T00:00:02Z', data: {} },
      ]
      const state = { ...initialState, events: existing }
      const next = reducer(state, { type: 'BACKFILL_EVENTS', data: backfill })
      expect(next.events).toHaveLength(4)
      expect(next.events.map(e => e.timestamp)).toEqual([
        '2024-01-01T00:00:04Z',
        '2024-01-01T00:00:03Z',
        '2024-01-01T00:00:02Z',
        '2024-01-01T00:00:01Z',
      ])
    })
  })
})
