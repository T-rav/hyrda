import React, { useState, useCallback, useEffect } from 'react'
import { HydraProvider, useHydra } from './context/HydraContext'
import { Header } from './components/Header'
import { WorkerList } from './components/WorkerList'
import { TranscriptView } from './components/TranscriptView'
import { HumanInputBanner } from './components/HumanInputBanner'
import { HITLTable } from './components/HITLTable'
import { Livestream } from './components/Livestream'
import { SystemPanel } from './components/SystemPanel'
import { MetricsPanel } from './components/MetricsPanel'
import { StreamView } from './components/StreamView'
import { theme } from './theme'
import { ACTIVE_STATUSES } from './constants'

const TABS = ['issues', 'transcript', 'hitl', 'livestream', 'metrics', 'system']

const TAB_LABELS = {
  issues: 'Work Stream',
  transcript: 'Transcript',
  hitl: 'HITL',
  livestream: 'Livestream',
  metrics: 'Metrics',
  system: 'System',
}

function SystemAlertBanner({ alert }) {
  if (!alert) return null
  return (
    <div style={styles.alertBanner}>
      <span style={styles.alertIcon}>!</span>
      <span>{alert.message}</span>
      {alert.source && <span style={styles.alertSource}>Source: {alert.source}</span>}
    </div>
  )
}

function AppContent() {
  const {
    connected, orchestratorStatus, workers, prs,
    mergedCount, sessionTriaged, sessionPlanned,
    sessionImplemented, sessionReviewed, config, events,
    hitlItems, humanInputRequests, submitHumanInput, refreshHitl,
    backgroundWorkers, metrics, systemAlert, intents,
    lifetimeStats, githubMetrics, phase, toggleBgWorker,
  } = useHydra()
  const [selectedWorker, setSelectedWorker] = useState(null)
  const [activeTab, setActiveTab] = useState('issues')
  const [expandedStages, setExpandedStages] = useState({})
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

  const handleViewTranscript = useCallback((issueNumber) => {
    const numKey = Number(issueNumber)
    if (workers[numKey]) {
      setSelectedWorker(numKey)
    } else if (workers[`plan-${issueNumber}`]) {
      setSelectedWorker(`plan-${issueNumber}`)
    } else if (workers[`triage-${issueNumber}`]) {
      setSelectedWorker(`triage-${issueNumber}`)
    }
    setActiveTab('transcript')
  }, [workers])

  const handleRequestChanges = useCallback(() => {
    setActiveTab('hitl')
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
        <SystemAlertBanner alert={systemAlert} />
        <HumanInputBanner requests={humanInputRequests} onSubmit={submitHumanInput} />

        <div style={styles.tabs}>
          {TABS.map((tab) => (
            <div
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={activeTab === tab ? tabActiveStyle : tabInactiveStyle}
            >
              {tab === 'hitl' ? (
                <>HITL{hitlItems?.length > 0 && <span style={hitlBadgeStyle}>{hitlItems.length}</span>}</>
              ) : TAB_LABELS[tab]}
            </div>
          ))}
        </div>

        <div style={styles.tabContent}>
          {activeTab === 'issues' && (
            <StreamView
              events={events}
              workers={workers}
              prs={prs}
              intents={intents}
              expandedStages={expandedStages}
              onToggleStage={setExpandedStages}
              onViewTranscript={handleViewTranscript}
              onRequestChanges={handleRequestChanges}
            />
          )}
          {activeTab === 'transcript' && (
            <TranscriptView workers={workers} selectedWorker={selectedWorker} />
          )}
          {activeTab === 'hitl' && <HITLTable items={hitlItems} onRefresh={refreshHitl} />}
          {activeTab === 'livestream' && <Livestream events={events} />}
          {activeTab === 'system' && <SystemPanel workers={workers} backgroundWorkers={backgroundWorkers} onToggleBgWorker={toggleBgWorker} />}
          {activeTab === 'metrics' && (
            <MetricsPanel
              metrics={metrics}
              lifetimeStats={lifetimeStats}
              githubMetrics={githubMetrics}
              sessionCounts={{
                triaged: sessionTriaged,
                planned: sessionPlanned,
                implemented: sessionImplemented,
                reviewed: sessionReviewed,
                merged: mergedCount,
              }}
            />
          )}
        </div>
      </div>

    </div>
  )
}

export default function App() {
  return (
    <HydraProvider>
      <AppContent />
    </HydraProvider>
  )
}

const styles = {
  layout: {
    display: 'grid',
    gridTemplateRows: 'auto 1fr',
    gridTemplateColumns: '280px 1fr',
    height: '100vh',
    minWidth: '1024px',
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
  hitlBadge: {
    background: theme.red,
    color: theme.white,
    fontSize: 10,
    fontWeight: 700,
    borderRadius: 10,
    padding: '1px 6px',
    marginLeft: 6,
  },
  alertBanner: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '8px 16px',
    background: theme.redSubtle,
    borderBottom: `2px solid ${theme.red}`,
    color: theme.red,
    fontSize: 13,
    fontWeight: 600,
  },
  alertIcon: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 20,
    height: 20,
    borderRadius: '50%',
    background: theme.red,
    color: theme.white,
    fontSize: 12,
    fontWeight: 700,
    flexShrink: 0,
  },
  alertSource: {
    marginLeft: 'auto',
    fontSize: 11,
    fontWeight: 400,
    opacity: 0.8,
  },
}

// Pre-computed tab style variants (avoids object spread in .map())
export const tabInactiveStyle = styles.tab
export const tabActiveStyle = { ...styles.tab, ...styles.tabActive }
export const hitlBadgeStyle = styles.hitlBadge
