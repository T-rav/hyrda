import { useEffect, useRef, useCallback, useReducer } from 'react'

const initialState = {
  connected: false,
  batchNum: 0,
  phase: 'idle',
  workers: {},    // { [issueNum]: WorkerState }
  prs: [],        // PRData[]
  reviews: [],    // ReviewData[]
  mergedCount: 0,
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

    case 'phase_change':
      return { ...state, phase: action.data.phase }

    case 'worker_update': {
      const { issue, status, worker } = action.data
      const existing = state.workers[issue] || {
        status: 'queued',
        worker,
        title: `Issue #${issue}`,
        branch: `agent/issue-${issue}`,
        transcript: [],
        pr: null,
      }
      return {
        ...state,
        workers: {
          ...state.workers,
          [issue]: { ...existing, status, worker },
        },
      }
    }

    case 'transcript_line': {
      const key = action.data.issue || action.data.pr
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
      }

    case 'review_update':
      if (action.data.status === 'done') {
        return {
          ...addEvent(state, action),
          reviews: [...state.reviews, action.data],
        }
      }
      return addEvent(state, action)

    case 'merge_update':
      return {
        ...addEvent(state, action),
        mergedCount: action.data.status === 'merge_requested'
          ? state.mergedCount + 1
          : state.mergedCount,
      }

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

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`)

    ws.onopen = () => dispatch({ type: 'CONNECTED' })

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        dispatch({ type: event.type, data: event.data, timestamp: event.timestamp })
      } catch { /* ignore parse errors */ }
    }

    ws.onclose = () => {
      dispatch({ type: 'DISCONNECTED' })
      reconnectTimer.current = setTimeout(connect, 2000)
    }

    ws.onerror = () => ws.close()
    wsRef.current = ws
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (wsRef.current) wsRef.current.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }
  }, [connect])

  return state
}
