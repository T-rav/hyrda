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
  issues: {},
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

  it('initial state includes issues map', () => {
    expect(initialState.issues).toEqual({})
  })

  it('INTENT_SUBMITTED adds issue to issues map', () => {
    const next = reducer(initialState, {
      type: 'INTENT_SUBMITTED',
      data: { issueNumber: 99, title: 'Add caching', text: 'Add caching to API' },
    })
    expect(next.issues[99]).toBeDefined()
    expect(next.issues[99].number).toBe(99)
    expect(next.issues[99].title).toBe('Add caching')
    expect(next.issues[99].body).toBe('Add caching to API')
    expect(next.issues[99].status).toBe('submitted')
  })

  it('worker_update creates issue entry with implementing status', () => {
    const next = reducer(initialState, {
      type: 'worker_update',
      data: { issue: 42, status: 'running', worker: 0, role: 'implementer' },
    })
    expect(next.issues[42]).toBeDefined()
    expect(next.issues[42].status).toBe('implementing')
  })

  it('worker_update sets issue status to done', () => {
    const state = { ...initialState }
    const next = reducer(state, {
      type: 'worker_update',
      data: { issue: 42, status: 'done', worker: 0, role: 'implementer' },
    })
    expect(next.issues[42].status).toBe('done')
  })

  it('worker_update sets issue status to failed', () => {
    const next = reducer(initialState, {
      type: 'worker_update',
      data: { issue: 42, status: 'failed', worker: 0, role: 'implementer' },
    })
    expect(next.issues[42].status).toBe('failed')
  })

  it('triage_update creates issue with triaging status', () => {
    const next = reducer(initialState, {
      type: 'triage_update',
      data: { issue: 10, status: 'evaluating', worker: 0 },
      timestamp: '2024-01-01T00:00:00Z',
    })
    expect(next.issues[10]).toBeDefined()
    expect(next.issues[10].status).toBe('triaging')
  })

  it('planner_update creates issue with planning status', () => {
    const next = reducer(initialState, {
      type: 'planner_update',
      data: { issue: 20, status: 'planning', worker: 0 },
      timestamp: '2024-01-01T00:00:00Z',
    })
    expect(next.issues[20]).toBeDefined()
    expect(next.issues[20].status).toBe('planning')
  })

  it('planner_update saves plan summary', () => {
    const next = reducer(initialState, {
      type: 'planner_update',
      data: { issue: 20, status: 'done', worker: 0, summary: 'Add middleware' },
      timestamp: '2024-01-01T00:00:00Z',
    })
    expect(next.issues[20].planSummary).toBe('Add middleware')
  })

  it('pr_created attaches PR info to issue', () => {
    const next = reducer(initialState, {
      type: 'pr_created',
      data: { issue: 42, pr: 101, url: 'https://github.com/test/pull/101' },
      timestamp: '2024-01-01T00:00:00Z',
    })
    expect(next.issues[42]).toBeDefined()
    expect(next.issues[42].prNumber).toBe(101)
    expect(next.issues[42].prUrl).toBe('https://github.com/test/pull/101')
  })

  it('review_update sets issue to reviewing', () => {
    const next = reducer(initialState, {
      type: 'review_update',
      data: { issue: 42, pr: 101, status: 'reviewing', worker: 0 },
      timestamp: '2024-01-01T00:00:00Z',
    })
    expect(next.issues[42]).toBeDefined()
    expect(next.issues[42].status).toBe('reviewing')
  })

  it('merge_update sets issue to merged', () => {
    const next = reducer(initialState, {
      type: 'merge_update',
      data: { issue: 42, pr: 101, status: 'merged' },
      timestamp: '2024-01-01T00:00:00Z',
    })
    expect(next.issues[42]).toBeDefined()
    expect(next.issues[42].status).toBe('merged')
  })

  it('phase_change resets issues on new run', () => {
    const state = {
      ...initialState,
      phase: 'idle',
      issues: { 1: { number: 1, status: 'merged' } },
    }
    const next = reducer(state, {
      type: 'phase_change',
      data: { phase: 'plan' },
      timestamp: new Date().toISOString(),
    })
    expect(next.issues).toEqual({})
  })
})
