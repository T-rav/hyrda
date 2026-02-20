import React, { useState, useCallback, useEffect } from 'react'
import { useHydraSocket } from './hooks/useHydraSocket'
import { Header } from './components/Header'
import { WorkerList } from './components/WorkerList'
import { TranscriptView } from './components/TranscriptView'
import { PRTable } from './components/PRTable'
import { HumanInputBanner } from './components/HumanInputBanner'
import { HITLTable } from './components/HITLTable'
import { theme } from './theme'

const TABS = ['transcript', 'prs', 'hitl', 'timeline']
const ACTIVE_STATUSES = ['running', 'testing', 'committing', 'reviewing', 'planning', 'evaluating', 'quality_fix']

export default function App() {
  const {
    connected, batchNum, phase, orchestratorStatus, workers, reviews,
    mergedCount, sessionPrsCount, sessionTriaged, sessionPlanned,
    sessionImplemented, sessionReviewed, lifetimeStats, config, events,
    hitlItems, humanInputRequests, submitHumanInput, refreshHitl,
  } = useHydraSocket()
  const [selectedWorker, setSelectedWorker] = useState(null)
  const [activeTab, setActiveTab] = useState('transcript')
  const handleWorkerSelect = useCallback((worker) => {
    setSelectedWorker(worker)
    setActiveTab('transcript')
  }, [])

  // Auto-select the first active worker when none is selected
  useEffect(() => {
    if (selectedWorker !== null && workers[selectedWorker]) return
    const active = Object.entries(workers).find(
      ([, w]) => ACTIVE_STATUSES.includes(w.status)
    )
    if (active) {
      const key = active[0]
      setSelectedWorker(isNaN(Number(key)) ? key : Number(key))
    }
  }, [workers, selectedWorker])

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
          triage: sessionTriaged,
          plan: sessionPlanned,
          implement: sessionImplemented,
          review: sessionReviewed,
          merged: mergedCount,
        }}
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
        <HumanInputBanner requests={humanInputRequests} onSubmit={submitHumanInput} />

        <div style={styles.tabs}>
          {TABS.map((tab) => (
            <div
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={activeTab === tab ? tabActiveStyle : tabInactiveStyle}
            >
              {tab === 'prs' ? 'Pull Requests' : tab === 'hitl' ? (
                <>HITL{hitlItems?.length > 0 && <span style={hitlBadgeStyle}>{hitlItems.length}</span>}</>
              ) : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </div>
          ))}
        </div>

        <div style={styles.tabContent}>
          {activeTab === 'transcript' && (
            <TranscriptView workers={workers} selectedWorker={selectedWorker} />
          )}
          {activeTab === 'prs' && <PRTable />}
          {activeTab === 'hitl' && <HITLTable items={hitlItems} onRefresh={refreshHitl} />}
          {activeTab === 'timeline' && (
            <div style={styles.timeline}>
              {events.map((e, i) => (
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
    borderBottom: `1px solid ${theme.border}`,
    background: theme.surface,
  },
  tab: {
    padding: '10px 20px',
    fontSize: 12,
    fontWeight: 600,
    color: theme.textMuted,
    cursor: 'pointer',
    borderBottom: '2px solid transparent',
    transition: 'all 0.15s',
  },
  tabActive: {
    color: theme.accent,
    borderBottomColor: theme.accent,
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
    borderBottom: `1px solid ${theme.border}`,
    fontSize: 11,
  },
  timelineTime: { color: theme.textMuted, marginRight: 8 },
  timelineType: { fontWeight: 600, color: theme.accent, marginRight: 6 },
  hitlBadge: {
    background: theme.red,
    color: theme.white,
    fontSize: 10,
    fontWeight: 700,
    borderRadius: 10,
    padding: '1px 6px',
    marginLeft: 6,
  },
}

// Pre-computed tab style variants (avoids object spread in .map())
export const tabInactiveStyle = styles.tab
export const tabActiveStyle = { ...styles.tab, ...styles.tabActive }
export const hitlBadgeStyle = styles.hitlBadge
