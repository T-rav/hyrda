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

  describe('triage_update status mapping', () => {
    it('maps evaluating status to evaluating (not running)', () => {
      const next = reducer(initialState, {
        type: 'triage_update',
        data: { issue: 10, status: 'evaluating', worker: 0 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.workers['triage-10'].status).toBe('evaluating')
      expect(next.workers['triage-10'].role).toBe('triage')
    })

    it('maps done status to done', () => {
      const next = reducer(initialState, {
        type: 'triage_update',
        data: { issue: 10, status: 'done', worker: 0 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.workers['triage-10'].status).toBe('done')
    })

    it('maps failed status to failed', () => {
      const next = reducer(initialState, {
        type: 'triage_update',
        data: { issue: 10, status: 'failed', worker: 0 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.workers['triage-10'].status).toBe('failed')
    })

    it('maps unknown triage status to evaluating', () => {
      const next = reducer(initialState, {
        type: 'triage_update',
        data: { issue: 10, status: 'something_else', worker: 0 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.workers['triage-10'].status).toBe('evaluating')
    })
  })

  describe('planner_update status mapping', () => {
    it('maps planning status to planning (not running)', () => {
      const next = reducer(initialState, {
        type: 'planner_update',
        data: { issue: 20, status: 'planning', worker: 1 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.workers['plan-20'].status).toBe('planning')
      expect(next.workers['plan-20'].role).toBe('planner')
    })

    it('maps done status to done', () => {
      const next = reducer(initialState, {
        type: 'planner_update',
        data: { issue: 20, status: 'done', worker: 1 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.workers['plan-20'].status).toBe('done')
    })

    it('maps failed status to failed', () => {
      const next = reducer(initialState, {
        type: 'planner_update',
        data: { issue: 20, status: 'failed', worker: 1 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.workers['plan-20'].status).toBe('failed')
    })
  })

  describe('review_update status mapping', () => {
    it('maps reviewing status to reviewing (not running)', () => {
      const next = reducer(initialState, {
        type: 'review_update',
        data: { pr: 30, issue: 15, status: 'reviewing', worker: 2 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.workers['review-30'].status).toBe('reviewing')
      expect(next.workers['review-30'].role).toBe('reviewer')
    })

    it('maps done status to done and appends to reviews', () => {
      const next = reducer(initialState, {
        type: 'review_update',
        data: { pr: 30, issue: 15, status: 'done', worker: 2 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.workers['review-30'].status).toBe('done')
      expect(next.reviews).toHaveLength(1)
    })

    it('maps in-progress status to reviewing', () => {
      const next = reducer(initialState, {
        type: 'review_update',
        data: { pr: 30, issue: 15, status: 'in_progress', worker: 2 },
        timestamp: '2024-01-01T00:00:00Z',
      })
      expect(next.workers['review-30'].status).toBe('reviewing')
    })
  })
})
