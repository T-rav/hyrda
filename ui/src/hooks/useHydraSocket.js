import { useEffect, useRef, useCallback, useReducer } from 'react'

const initialState = {
  connected: false,
  batchNum: 0,
  phase: 'idle',
  orchestratorStatus: 'idle',  // idle | running | stopping | done
  workers: {},    // { [issueNum]: WorkerState }
  prs: [],        // PRData[]
  reviews: [],    // ReviewData[]
  mergedCount: 0,
  sessionPrsCount: 0,
  lifetimeStats: null,  // { issues_completed, prs_merged, issues_created }
  config: null,   // { max_workers, max_planners, max_reviewers }
  events: [],     // HydraEvent[] (most recent first)
}

function reducer(state, action) {
  switch (action.type) {
    case 'CONNECTED':
      return { ...state, connected: true }
    case 'DISCONNECTED':
      return { ...state, connected: false }

    case 'batch_start':
      return { ...state, batchNum: action.data.batch }

    case 'phase_change': {
      const newPhase = action.data.phase
      // Reset run state when starting a new run (idle/done → plan or fetch)
      const isNewRun = (newPhase === 'plan' || newPhase === 'implement')
        && (state.phase === 'idle' || state.phase === 'done')
      if (isNewRun) {
        return {
          ...addEvent(state, action),
          phase: newPhase,
          workers: {},
          prs: [],
          reviews: [],
          mergedCount: 0,
          sessionPrsCount: 0,
        }
      }
      return { ...addEvent(state, action), phase: newPhase }
    }

    case 'orchestrator_status':
      return {
        ...addEvent(state, action),
        orchestratorStatus: action.data.status,
      }

    case 'worker_update': {
      const { issue, status, worker, role } = action.data
      const existing = state.workers[issue] || {
        status: 'queued',
        worker,
        role: role || 'implementer',
        title: `Issue #${issue}`,
        branch: `agent/issue-${issue}`,
        transcript: [],
        pr: null,
      }
      return {
        ...state,
        workers: {
          ...state.workers,
          [issue]: { ...existing, status, worker, role: role || existing.role },
        },
      }
    }

    case 'transcript_line': {
      let key = action.data.issue || action.data.pr
      if (action.data.source === 'triage') {
        key = `triage-${action.data.issue}`
      } else if (action.data.source === 'planner') {
        key = `plan-${action.data.issue}`
      } else if (action.data.source === 'reviewer') {
        key = `review-${action.data.pr}`
      }
      if (!key || !state.workers[key]) return addEvent(state, action)
      const w = state.workers[key]
      return {
        ...addEvent(state, action),
        workers: {
          ...state.workers,
          [key]: { ...w, transcript: [...w.transcript, action.data.line] },
        },
      }
    }

    case 'pr_created':
      return {
        ...addEvent(state, action),
        prs: [...state.prs, action.data],
        sessionPrsCount: state.sessionPrsCount + 1,
      }

    case 'triage_update': {
      const triageKey = `triage-${action.data.issue}`
      const triageStatus = action.data.status === 'done' ? 'done' : 'running'
      const triageWorker = {
        status: triageStatus,
        worker: action.data.worker,
        role: 'triage',
        title: `Triage Issue #${action.data.issue}`,
        branch: '',
        transcript: [],
        pr: null,
      }
      const existingTriage = state.workers[triageKey]
      return {
        ...addEvent(state, action),
        workers: {
          ...state.workers,
          [triageKey]: existingTriage
            ? { ...existingTriage, status: triageStatus }
            : triageWorker,
        },
      }
    }

    case 'planner_update': {
      const planKey = `plan-${action.data.issue}`
      const planStatus = action.data.status === 'done' ? 'done'
        : action.data.status === 'failed' ? 'failed' : 'running'
      const planWorker = {
        status: planStatus,
        worker: action.data.worker,
        role: 'planner',
        title: `Plan Issue #${action.data.issue}`,
        branch: '',
        transcript: [],
        pr: null,
      }
      const existingPlanner = state.workers[planKey]
      return {
        ...addEvent(state, action),
        workers: {
          ...state.workers,
          [planKey]: existingPlanner
            ? { ...existingPlanner, status: planStatus }
            : planWorker,
        },
      }
    }

    case 'review_update': {
      const reviewKey = `review-${action.data.pr}`
      const reviewStatus = action.data.status === 'done' ? 'done' : 'running'
      const reviewWorker = {
        status: reviewStatus,
        worker: action.data.worker,
        role: 'reviewer',
        title: `PR #${action.data.pr} (Issue #${action.data.issue})`,
        branch: '',
        transcript: [],
        pr: action.data.pr,
      }
      const existingReviewer = state.workers[reviewKey]
      const updatedWorkers = {
        ...state.workers,
        [reviewKey]: existingReviewer
          ? { ...existingReviewer, status: reviewStatus }
          : reviewWorker,
      }
      if (action.data.status === 'done') {
        return {
          ...addEvent(state, action),
          workers: updatedWorkers,
          reviews: [...state.reviews, action.data],
        }
      }
      return { ...addEvent(state, action), workers: updatedWorkers }
    }

    case 'merge_update': {
      const isMerged = action.data.status === 'merged'
      const updatedPrs = isMerged && action.data.pr
        ? state.prs.map(p => p.pr === action.data.pr ? { ...p, merged: true } : p)
        : state.prs
      return {
        ...addEvent(state, action),
        prs: updatedPrs,
        mergedCount: isMerged
          ? state.mergedCount + 1
          : state.mergedCount,
      }
    }

    case 'LIFETIME_STATS':
      return { ...state, lifetimeStats: action.data }

    case 'CONFIG':
      return { ...state, config: action.data }

    case 'EXISTING_PRS':
      return { ...state, prs: [...action.data, ...state.prs] }

    case 'batch_complete':
      return {
        ...addEvent(state, action),
        mergedCount: action.data.merged || state.mergedCount,
      }

    case 'error':
      return addEvent(state, action)

    default:
      return addEvent(state, action)
  }
}

function addEvent(state, action) {
  const event = { type: action.type, timestamp: action.timestamp, data: action.data }
  return { ...state, events: [event, ...state.events].slice(0, 500) }
}

export function useHydraSocket() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)

  const fetchLifetimeStats = useCallback(() => {
    fetch('/api/stats')
      .then(r => r.json())
      .then(data => dispatch({ type: 'LIFETIME_STATS', data }))
      .catch(() => {})
  }, [])

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`)

    ws.onopen = () => {
      dispatch({ type: 'CONNECTED' })
      // Fetch initial orchestrator status on connect
      fetch('/api/control/status')
        .then(r => r.json())
        .then(data => {
          dispatch({
            type: 'orchestrator_status',
            data: { status: data.status },
            timestamp: new Date().toISOString(),
          })
          if (data.config) {
            dispatch({ type: 'CONFIG', data: data.config })
          }
        })
        .catch(() => {})
      // Fetch lifetime stats on connect
      fetchLifetimeStats()
      // Fetch existing PRs from GitHub
      fetch('/api/prs')
        .then(r => r.json())
        .then(data => dispatch({ type: 'EXISTING_PRS', data }))
        .catch(() => {})
    }

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        dispatch({ type: event.type, data: event.data, timestamp: event.timestamp })
        if (event.type === 'batch_complete') fetchLifetimeStats()
      } catch { /* ignore parse errors */ }
    }

    ws.onclose = () => {
      dispatch({ type: 'DISCONNECTED' })
      reconnectTimer.current = setTimeout(connect, 2000)
    }

    ws.onerror = () => ws.close()
    wsRef.current = ws
  }, [fetchLifetimeStats])

  useEffect(() => {
    connect()
    return () => {
      if (wsRef.current) wsRef.current.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }
  }, [connect])

  return state
}
