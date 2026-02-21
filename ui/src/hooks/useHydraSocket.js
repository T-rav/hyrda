import { useEffect, useRef, useCallback, useReducer } from 'react'
import { MAX_EVENTS } from '../constants'

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
  sessionTriaged: 0,
  sessionPlanned: 0,
  sessionImplemented: 0,
  sessionReviewed: 0,
  lifetimeStats: null,  // { issues_completed, prs_merged, issues_created }
  config: null,   // { max_workers, max_planners, max_reviewers }
  events: [],     // HydraEvent[] (most recent first)
  hitlItems: [],  // HITLItem[]
  humanInputRequests: {},  // Record<string, string>
  backgroundWorkers: [],  // BackgroundWorkerState[]
  metrics: null,  // MetricsData | null
}

export const SESSION_RESET = {
  workers: {},
  prs: [],
  reviews: [],
  hitlItems: [],
  sessionTriaged: 0,
  sessionPlanned: 0,
  sessionImplemented: 0,
  sessionReviewed: 0,
  mergedCount: 0,
  sessionPrsCount: 0,
}

export function reducer(state, action) {
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
          ...SESSION_RESET,
        }
      }
      return { ...addEvent(state, action), phase: newPhase }
    }

    case 'orchestrator_status': {
      const newStatus = action.data.status
      const isStopped = newStatus === 'idle' || newStatus === 'done' || newStatus === 'stopping'
      const isStarting = newStatus === 'running' && state.orchestratorStatus !== 'running'
      return {
        ...addEvent(state, action),
        orchestratorStatus: newStatus,
        ...(isStarting ? SESSION_RESET : {}),
        ...(isStopped ? {
          workers: {},
          sessionTriaged: 0,
          sessionPlanned: 0,
          sessionImplemented: 0,
          sessionReviewed: 0,
          mergedCount: 0,
          sessionPrsCount: 0,
        } : {}),
      }
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
      const prevStatus = existing?.status
      const newImplemented = status === 'done' && prevStatus !== 'done'
        ? state.sessionImplemented + 1 : state.sessionImplemented
      return {
        ...state,
        sessionImplemented: newImplemented,
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
      const newTriaged = triageStatus === 'done' && existingTriage?.status !== 'done'
        ? state.sessionTriaged + 1 : state.sessionTriaged
      return {
        ...addEvent(state, action),
        sessionTriaged: newTriaged,
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
      const planStatus = action.data.status
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
      const newPlanned = planStatus === 'done' && existingPlanner?.status !== 'done'
        ? state.sessionPlanned + 1 : state.sessionPlanned
      return {
        ...addEvent(state, action),
        sessionPlanned: newPlanned,
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
      const reviewStatus = action.data.status
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
      const newReviewed = reviewStatus === 'done' && existingReviewer?.status !== 'done'
        ? state.sessionReviewed + 1 : state.sessionReviewed
      const updatedWorkers = {
        ...state.workers,
        [reviewKey]: existingReviewer
          ? { ...existingReviewer, status: reviewStatus }
          : reviewWorker,
      }
      if (action.data.status === 'done') {
        return {
          ...addEvent(state, action),
          sessionReviewed: newReviewed,
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

    case 'HITL_ITEMS':
      return { ...state, hitlItems: action.data }

    case 'HUMAN_INPUT_REQUESTS':
      return { ...state, humanInputRequests: action.data }

    case 'HUMAN_INPUT_SUBMITTED': {
      const next = { ...state.humanInputRequests }
      delete next[action.data.issueNumber]
      return { ...state, humanInputRequests: next }
    }

    case 'batch_complete':
      return {
        ...addEvent(state, action),
        mergedCount: action.data.merged || state.mergedCount,
      }

    case 'hitl_update':
      return {
        ...addEvent(state, action),
        hitlUpdate: action.data,
      }

    case 'background_worker_status': {
      const { worker, status, last_run, details } = action.data
      const existing = state.backgroundWorkers.filter(w => w.name !== worker)
      return {
        ...addEvent(state, action),
        backgroundWorkers: [...existing, { name: worker, status, last_run, details }],
      }
    }

    case 'BACKGROUND_WORKERS':
      return { ...state, backgroundWorkers: action.data }

    case 'METRICS':
      return { ...state, metrics: action.data }

    case 'error':
      return addEvent(state, action)

    case 'BACKFILL_EVENTS': {
      const existingKeys = new Set(
        state.events.map(e => `${e.type}|${e.timestamp}`)
      )
      const newEvents = action.data
        .map(e => ({ type: e.type, timestamp: e.timestamp, data: e.data }))
        .filter(e => !existingKeys.has(`${e.type}|${e.timestamp}`))
      const merged = [...state.events, ...newEvents]
        .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
        .slice(0, MAX_EVENTS)
      return { ...state, events: merged }
    }

    default:
      return addEvent(state, action)
  }
}

function addEvent(state, action) {
  const event = { type: action.type, timestamp: action.timestamp, data: action.data }
  return { ...state, events: [event, ...state.events].slice(0, MAX_EVENTS) }
}

export function useHydraSocket() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const lastEventTsRef = useRef(null)

  const fetchLifetimeStats = useCallback(() => {
    fetch('/api/stats')
      .then(r => r.json())
      .then(data => dispatch({ type: 'LIFETIME_STATS', data }))
      .catch(() => {})
  }, [])

  const fetchHitlItems = useCallback(() => {
    fetch('/api/hitl')
      .then(r => r.json())
      .then(data => dispatch({ type: 'HITL_ITEMS', data }))
      .catch(() => {})
  }, [])

  const submitHumanInput = useCallback(async (issueNumber, answer) => {
    try {
      await fetch(`/api/human-input/${issueNumber}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer }),
      })
      dispatch({ type: 'HUMAN_INPUT_SUBMITTED', data: { issueNumber } })
    } catch { /* ignore */ }
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
      // Fetch HITL items on connect
      fetchHitlItems()
      // Fetch background worker status on connect
      fetch('/api/system/workers')
        .then(r => r.json())
        .then(data => dispatch({ type: 'BACKGROUND_WORKERS', data: data.workers }))
        .catch(() => {})
      // Fetch metrics on connect
      fetch('/api/metrics')
        .then(r => r.json())
        .then(data => dispatch({ type: 'METRICS', data }))
        .catch(() => {})
      // On reconnect, backfill missed events from disk-backed API
      if (lastEventTsRef.current) {
        fetch(`/api/events?since=${encodeURIComponent(lastEventTsRef.current)}`)
          .then(r => r.json())
          .then(events => dispatch({ type: 'BACKFILL_EVENTS', data: events }))
          .catch(() => {})
      }
    }

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        dispatch({ type: event.type, data: event.data, timestamp: event.timestamp })
        if (event.timestamp && (!lastEventTsRef.current || event.timestamp > lastEventTsRef.current)) {
          lastEventTsRef.current = event.timestamp
        }
        if (event.type === 'batch_complete') {
          fetchLifetimeStats()
          fetch('/api/metrics').then(r => r.json()).then(data => dispatch({ type: 'METRICS', data })).catch(() => {})
        }
        if (event.type === 'hitl_update') fetchHitlItems()
      } catch { /* ignore parse errors */ }
    }

    ws.onclose = () => {
      dispatch({ type: 'DISCONNECTED' })
      reconnectTimer.current = setTimeout(connect, 2000)
    }

    ws.onerror = () => ws.close()
    wsRef.current = ws
  }, [fetchLifetimeStats, fetchHitlItems])

  // Poll for human input requests every 3 seconds
  useEffect(() => {
    const poll = () => {
      fetch('/api/human-input')
        .then(r => r.ok ? r.json() : {})
        .then(data => dispatch({ type: 'HUMAN_INPUT_REQUESTS', data }))
        .catch(() => {})
    }
    poll()
    const interval = setInterval(poll, 3000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (wsRef.current) wsRef.current.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }
  }, [connect])

  return { ...state, submitHumanInput, refreshHitl: fetchHitlItems }
}
