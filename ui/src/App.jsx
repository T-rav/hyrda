import React, { useState, useCallback, useEffect } from 'react'
import { HydraProvider, useHydra } from './context/HydraContext'
import { Header } from './components/Header'
import { TranscriptView } from './components/TranscriptView'
import { HumanInputBanner } from './components/HumanInputBanner'
import { HITLTable } from './components/HITLTable'
import { SystemPanel } from './components/SystemPanel'
import { MetricsPanel } from './components/MetricsPanel'
import { StreamView } from './components/StreamView'
import { PipelineControlPanel } from './components/PipelineControlPanel'
import { theme } from './theme'
import { ACTIVE_STATUSES } from './constants'

const TABS = ['issues', 'transcript', 'hitl', 'metrics', 'system']

const TAB_LABELS = {
  issues: 'Work Stream',
  transcript: 'Transcript',
  hitl: 'HITL',
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
    hitlItems, humanInputRequests, submitHumanInput, refreshHitl,
    backgroundWorkers, systemAlert, intents, toggleBgWorker, updateBgWorkerInterval,
    requestChanges,
  } = useHydra()
  const [selectedWorker, setSelectedWorker] = useState(null)
  const [activeTab, setActiveTab] = useState('issues')
  const [expandedStages, setExpandedStages] = useState({})
  const [pipelinePanelOpen, setPipelinePanelOpen] = useState(true)

  // Auto-select the first active worker when none is selected
  useEffect(() => {
    if (selectedWorker !== null && (workers[selectedWorker] || (typeof selectedWorker === 'string' && selectedWorker.startsWith('bg-')))) return
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

  const handleViewTranscript = useCallback((key) => {
    if (typeof key === 'string' && key.startsWith('bg-')) {
      setSelectedWorker(key)
    } else {
      const numKey = Number(key)
      if (workers[numKey]) {
        setSelectedWorker(numKey)
      } else if (workers[`plan-${key}`]) {
        setSelectedWorker(`plan-${key}`)
      } else if (workers[`triage-${key}`]) {
        setSelectedWorker(`triage-${key}`)
      }
    }
    setActiveTab('transcript')
  }, [workers])

  const handleRequestChanges = useCallback(async (issueNumber, feedback, stage) => {
    const ok = await requestChanges(issueNumber, feedback, stage)
    if (ok) {
      setActiveTab('hitl')
    }
    return ok
  }, [requestChanges])

  const handleTogglePipelinePanel = useCallback(() => {
    setPipelinePanelOpen(prev => !prev)
  }, [])

  return (
    <div style={styles.layout}>
      <Header
        connected={connected}
        orchestratorStatus={orchestratorStatus}
        onStart={handleStart}
        onStop={handleStop}
        pipelinePanelOpen={pipelinePanelOpen}
        onTogglePipelinePanel={handleTogglePipelinePanel}
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

        <div style={styles.contentRow}>
          <div style={styles.tabContent}>
            {activeTab === 'issues' && (
              <StreamView
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
            {activeTab === 'system' && <SystemPanel backgroundWorkers={backgroundWorkers} onToggleBgWorker={toggleBgWorker} onViewLog={handleViewTranscript} onUpdateInterval={updateBgWorkerInterval} />}
            {activeTab === 'metrics' && <MetricsPanel />}
          </div>
          <PipelineControlPanel
            collapsed={!pipelinePanelOpen}
            onToggleCollapse={handleTogglePipelinePanel}
            onToggleBgWorker={toggleBgWorker}
          />
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
    gridTemplateColumns: '1fr',
    height: '100vh',
    minWidth: '800px',
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
  contentRow: {
    flex: 1,
    display: 'flex',
    overflow: 'hidden',
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
