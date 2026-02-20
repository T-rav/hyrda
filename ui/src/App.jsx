import React, { useState, useCallback } from 'react'
import { useHydraSocket } from './hooks/useHydraSocket'
import { Header } from './components/Header'
import { WorkerList } from './components/WorkerList'
import { TranscriptView } from './components/TranscriptView'
import { IntentInput } from './components/IntentInput'
import { StreamView } from './components/StreamView'
import { theme } from './theme'

export default function App() {
  const {
    connected, phase, orchestratorStatus, workers,
    mergedCount, sessionPrsCount, lifetimeStats, config, issues,
    hitlItems, humanInputRequests, dispatch, submitHumanInput, refreshHitl,
  } = useHydraSocket()
  const [selectedWorker, setSelectedWorker] = useState(null)

  const handleWorkerSelect = useCallback((worker) => {
    setSelectedWorker(worker)
  }, [])

  const handleCloseTranscript = useCallback(() => {
    setSelectedWorker(null)
  }, [])

  const handleStart = useCallback(async () => {
    try {
      await fetch('/api/control/start', { method: 'POST' })
    } catch { /* ignore */ }
  }, [])

  const handleStop = useCallback(async () => {
    try {
      await fetch('/api/control/stop', { method: 'POST' })
    } catch { /* ignore */ }
  }, [])

  const handleIntent = useCallback(async (text) => {
    const resp = await fetch('/api/intent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
    if (resp.ok) {
      const data = await resp.json()
      dispatch({
        type: 'INTENT_SUBMITTED',
        data: {
          issueNumber: data.issue_number,
          title: data.title,
          text,
        },
      })
    }
  }, [dispatch])

  return (
    <div style={styles.layout}>
      <Header
        prsCount={sessionPrsCount}
        mergedCount={mergedCount}
        issuesFound={lifetimeStats?.issues_created ?? 0}
        connected={connected}
        orchestratorStatus={orchestratorStatus}
        onStart={handleStart}
        onStop={handleStop}
        phase={phase}
        workers={workers}
        config={config}
      />

      <WorkerList
        workers={workers}
        selectedWorker={selectedWorker}
        onSelect={handleWorkerSelect}
        humanInputRequests={humanInputRequests}
      />

      <div style={styles.main}>
        <IntentInput onSubmit={handleIntent} />

        <StreamView
          issues={issues}
          workers={workers}
          humanInputRequests={humanInputRequests}
          onHumanInputSubmit={submitHumanInput}
        />
      </div>

      {selectedWorker !== null && (
        <div style={styles.transcriptOverlay}>
          <div style={styles.transcriptPanel}>
            <div style={styles.transcriptHeader}>
              <span style={styles.transcriptTitle}>
                Worker #{selectedWorker}
              </span>
              <button
                style={styles.closeButton}
                onClick={handleCloseTranscript}
              >
                Close
              </button>
            </div>
            <TranscriptView workers={workers} selectedWorker={selectedWorker} />
          </div>
        </div>
      )}
    </div>
  )
}

const styles = {
  layout: {
    display: 'grid',
    gridTemplateRows: 'auto 1fr',
    gridTemplateColumns: '280px 1fr',
    height: '100vh',
    position: 'relative',
  },
  main: {
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  transcriptOverlay: {
    position: 'fixed',
    top: 0,
    right: 0,
    bottom: 0,
    width: '50%',
    minWidth: 400,
    maxWidth: 800,
    background: theme.overlay,
    zIndex: 100,
    display: 'flex',
  },
  transcriptPanel: {
    flex: 1,
    background: theme.bg,
    borderLeft: `1px solid ${theme.border}`,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  transcriptHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '10px 16px',
    borderBottom: `1px solid ${theme.border}`,
    background: theme.surface,
  },
  transcriptTitle: {
    fontWeight: 600,
    fontSize: 13,
    color: theme.textBright,
  },
  closeButton: {
    padding: '4px 12px',
    background: theme.surface,
    border: `1px solid ${theme.border}`,
    borderRadius: 6,
    color: theme.text,
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: 12,
  },
}

// Pre-computed style exports for testing
export const layoutStyle = styles.layout
export const mainStyle = styles.main
export const transcriptOverlayStyle = styles.transcriptOverlay
