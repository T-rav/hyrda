import React, { useState, useCallback, useEffect } from 'react'
import { useHydraSocket } from './hooks/useHydraSocket'
import { useHumanInput } from './hooks/useHumanInput'
import { Header } from './components/Header'
import { WorkerList } from './components/WorkerList'
import { TranscriptView } from './components/TranscriptView'
import { PRTable } from './components/PRTable'
import { HumanInputBanner } from './components/HumanInputBanner'
import { HITLTable } from './components/HITLTable'

const TABS = ['transcript', 'prs', 'hitl', 'timeline']
const ACTIVE_STATUSES = ['running', 'testing', 'committing', 'reviewing', 'planning']

export default function App() {
  const state = useHydraSocket()
  const { requests, submit } = useHumanInput()
  const [selectedWorker, setSelectedWorker] = useState(null)
  const [activeTab, setActiveTab] = useState('transcript')

  // Auto-select the first active worker when none is selected
  useEffect(() => {
    if (selectedWorker !== null && state.workers[selectedWorker]) return
    const active = Object.entries(state.workers).find(
      ([, w]) => ACTIVE_STATUSES.includes(w.status)
    )
    if (active) {
      const key = active[0]
      setSelectedWorker(isNaN(Number(key)) ? key : Number(key))
    }
  }, [state.workers, selectedWorker])

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

  return (
    <div style={styles.layout}>
      <Header
        sessionCounts={{
          triage: state.sessionTriaged,
          plan: state.sessionPlanned,
          implement: state.sessionImplemented,
          review: state.sessionReviewed,
          merged: state.mergedCount,
        }}
        connected={state.connected}
        orchestratorStatus={state.orchestratorStatus}
        onStart={handleStart}
        onStop={handleStop}
        phase={state.phase}
        workers={state.workers}
        config={state.config}
      />

      <WorkerList
        workers={state.workers}
        selectedWorker={selectedWorker}
        onSelect={setSelectedWorker}
        humanInputRequests={requests}
      />

      <div style={styles.main}>
        <HumanInputBanner requests={requests} onSubmit={submit} />

        <div style={styles.tabs}>
          {TABS.map((tab) => (
            <div
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={activeTab === tab ? tabActiveStyle : tabInactiveStyle}
            >
              {tab === 'prs' ? 'Pull Requests' : tab === 'hitl' ? 'HITL' : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </div>
          ))}
        </div>

        <div style={styles.tabContent}>
          {activeTab === 'transcript' && (
            <TranscriptView workers={state.workers} selectedWorker={selectedWorker} />
          )}
          {activeTab === 'prs' && <PRTable prs={state.prs} />}
          {activeTab === 'hitl' && <HITLTable />}
          {activeTab === 'timeline' && (
            <div style={styles.timeline}>
              {state.events.map((e, i) => (
                <div key={i} style={styles.timelineItem}>
                  <span style={styles.timelineTime}>
                    {new Date(e.timestamp).toLocaleTimeString()}
                  </span>
                  <span style={styles.timelineType}>{e.type.replace(/_/g, ' ')}</span>
                  <span>{JSON.stringify(e.data).slice(0, 120)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

    </div>
  )
}

const styles = {
  layout: {
    display: 'grid',
    gridTemplateRows: 'auto 1fr',
    gridTemplateColumns: '280px 1fr',
    height: '100vh',
  },
  main: {
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  tabs: {
    display: 'flex',
    borderBottom: '1px solid #30363d',
    background: '#161b22',
  },
  tab: {
    padding: '10px 20px',
    fontSize: 12,
    fontWeight: 600,
    color: '#8b949e',
    cursor: 'pointer',
    borderBottom: '2px solid transparent',
    transition: 'all 0.15s',
  },
  tabActive: {
    color: '#58a6ff',
    borderBottomColor: '#58a6ff',
  },
  tabContent: {
    flex: 1,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  timeline: {
    flex: 1,
    overflowY: 'auto',
    padding: 8,
  },
  timelineItem: {
    padding: '6px 8px',
    borderBottom: '1px solid #30363d',
    fontSize: 11,
  },
  timelineTime: { color: '#8b949e', marginRight: 8 },
  timelineType: { fontWeight: 600, color: '#58a6ff', marginRight: 6 },
}

// Pre-computed tab style variants (avoids object spread in .map())
export const tabInactiveStyle = styles.tab
export const tabActiveStyle = { ...styles.tab, ...styles.tabActive }
