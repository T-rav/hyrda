import React, { useState } from 'react'
import { theme } from '../theme'
import { BACKGROUND_WORKERS, INTERVAL_PRESETS, EDITABLE_INTERVAL_WORKERS } from '../constants'
import { useHydra } from '../context/HydraContext'
import { Livestream } from './Livestream'

const SUB_TABS = [
  { key: 'workers', label: 'Workers' },
  { key: 'livestream', label: 'Livestream' },
]

function relativeTime(isoString) {
  if (!isoString) return 'never'
  const diff = Date.now() - new Date(isoString).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ago`
}

export function formatInterval(seconds) {
  if (seconds == null) return null
  if (seconds < 60) return `every ${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `every ${minutes}m`
  const hours = Math.floor(minutes / 60)
  const remainMinutes = minutes % 60
  if (remainMinutes === 0) return `every ${hours}h`
  return `every ${hours}h ${remainMinutes}m`
}

export function formatNextRun(lastRun, intervalSeconds) {
  if (!lastRun || !intervalSeconds) return null
  const nextTime = new Date(lastRun).getTime() + intervalSeconds * 1000
  const diff = nextTime - Date.now()
  if (diff <= 0) return 'now'
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `in ${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `in ${minutes}m`
  const hours = Math.floor(minutes / 60)
  const remainMinutes = minutes % 60
  if (remainMinutes === 0) return `in ${hours}h`
  return `in ${hours}h ${remainMinutes}m`
}

function statusColor(status) {
  if (status === 'ok') return theme.green
  if (status === 'error') return theme.red
  return theme.textInactive
}

function BackgroundWorkerCard({ def, state, pipelinePollerLastRun, orchestratorStatus, onToggleBgWorker, onViewLog, onUpdateInterval }) {
  const [showIntervalEditor, setShowIntervalEditor] = useState(false)
  const isPipelinePoller = def.key === 'pipeline_poller'
  const isSystem = def.system === true
  const orchRunning = orchestratorStatus === 'running'
  const isEditable = EDITABLE_INTERVAL_WORKERS.has(def.key)

  let dotColor, statusText, lastRun, details

  if (!orchRunning) {
    // Orchestrator not running — system workers stopped, non-system show toggle state
    lastRun = isPipelinePoller ? (pipelinePollerLastRun || null) : (state?.last_run || null)
    details = state?.details || {}
    if (isSystem) {
      dotColor = theme.red
      statusText = 'stopped'
    } else if (state?.enabled === false) {
      dotColor = theme.red
      statusText = 'off'
    } else {
      dotColor = theme.yellow
      statusText = 'idle'
    }
  } else if (isPipelinePoller) {
    // Pipeline poller is frontend-only
    lastRun = pipelinePollerLastRun || null
    details = {}
    dotColor = lastRun ? theme.green : theme.textInactive
    statusText = lastRun ? 'ok' : 'idle'
  } else if (isSystem) {
    // System workers: ok/error based on backend state
    if (!state || !state.status || state.status === 'disabled') {
      dotColor = theme.green
      statusText = 'ok'
    } else {
      dotColor = statusColor(state.status)
      statusText = state.status
    }
    lastRun = state?.last_run || null
    details = state?.details || {}
  } else if (!state) {
    dotColor = theme.yellow
    statusText = 'idle'
    lastRun = null
    details = {}
  } else if (state.enabled === false) {
    dotColor = theme.red
    statusText = 'off'
    lastRun = state.last_run || null
    details = state.details || {}
  } else {
    dotColor = statusColor(state.status || 'ok')
    statusText = state.status || 'ok'
    lastRun = state.last_run || null
    details = state.details || {}
  }

  const enabled = !isSystem && (state ? state.enabled !== false : true)
  const showToggle = onToggleBgWorker && !isSystem
  const isError = statusText === 'error' || statusText === 'stopped'
  const hasDetails = Object.keys(details).length > 0

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <span
          style={{ ...styles.dot, background: dotColor }}
          data-testid={`dot-${def.key}`}
        />
        <span style={styles.label}>{def.label}</span>
        {isSystem && <span style={styles.systemBadge}>system</span>}
        {isSystem ? (
          <span
            style={statusText === 'ok'
              ? styles.statusPillOk
              : styles.statusPillError}
            data-testid={`status-pill-${def.key}`}
          >
            {statusText}
          </span>
        ) : (
          <span style={styles.status}>{statusText}</span>
        )}
        {showToggle && (
          <button
            style={enabled ? styles.toggleOn : styles.toggleOff}
            onClick={() => onToggleBgWorker(def.key, !enabled)}
          >
            {enabled ? 'On' : 'Off'}
          </button>
        )}
      </div>
      <div style={styles.lastRun}>
        Last run: {relativeTime(lastRun)}
      </div>
      {state?.interval_seconds != null && (
        <div style={styles.scheduleRow} data-testid={`schedule-${def.key}`}>
          <span style={styles.scheduleText}>
            Runs {formatInterval(state.interval_seconds)}
          </span>
          {lastRun && (
            <span style={styles.nextRunText}>
              {' \u00b7 Next '}{formatNextRun(lastRun, state.interval_seconds)}
            </span>
          )}
          {isEditable && onUpdateInterval && (
            <span
              style={styles.editIntervalLink}
              onClick={() => setShowIntervalEditor(!showIntervalEditor)}
              data-testid={`edit-interval-${def.key}`}
            >
              {showIntervalEditor ? 'close' : 'edit'}
            </span>
          )}
        </div>
      )}
      {showIntervalEditor && isEditable && onUpdateInterval && (
        <div style={styles.intervalEditor} data-testid={`interval-editor-${def.key}`}>
          {INTERVAL_PRESETS.map((preset) => (
            <button
              key={preset.seconds}
              style={state?.interval_seconds === preset.seconds ? styles.presetActive : styles.presetButton}
              onClick={() => {
                onUpdateInterval(def.key, preset.seconds)
                setShowIntervalEditor(false)
              }}
              data-testid={`preset-${preset.label}`}
            >
              {preset.label}
            </button>
          ))}
        </div>
      )}
      {hasDetails && (
        <div style={isError ? (onViewLog ? styles.detailsErrorCompact : styles.detailsError) : styles.details}>
          {Object.entries(details).map(([k, v]) => (
            <div key={k} style={k === 'error' ? styles.errorRow : styles.detailRow}>
              <span style={isError ? styles.detailKeyError : styles.detailKey}>{k.replace(/_/g, ' ')}</span>
              <span style={isError ? styles.detailValueError : styles.detailValue}>{String(v)}</span>
            </div>
          ))}
        </div>
      )}
      {onViewLog && (
        <div style={styles.cardActions}>
          <span
            style={styles.viewLogLink}
            onClick={() => onViewLog(`bg-${def.key}`)}
            data-testid={`view-log-${def.key}`}
          >
            View Log
          </span>
        </div>
      )}
    </div>
  )
}

export function SystemPanel({ backgroundWorkers, onToggleBgWorker, onViewLog, onUpdateInterval }) {
  const { pipelinePollerLastRun, orchestratorStatus, events } = useHydra()
  const [activeSubTab, setActiveSubTab] = useState('workers')

  return (
    <div style={styles.container}>
      <div style={styles.subTabSidebar}>
        {SUB_TABS.map(tab => (
          <div
            key={tab.key}
            onClick={() => setActiveSubTab(tab.key)}
            style={activeSubTab === tab.key ? subTabActiveStyle : subTabInactiveStyle}
          >
            {tab.label}
          </div>
        ))}
      </div>
      <div style={styles.subTabContent}>
        {activeSubTab === 'workers' && (
          <div style={styles.workersContent}>
            <h3 style={styles.heading}>Background Workers</h3>
            <div style={styles.grid}>
              {BACKGROUND_WORKERS.map((def) => {
                const state = backgroundWorkers.find(w => w.name === def.key)
                return (
                  <BackgroundWorkerCard
                    key={def.key}
                    def={def}
                    state={state}
                    pipelinePollerLastRun={pipelinePollerLastRun}
                    orchestratorStatus={orchestratorStatus}
                    onToggleBgWorker={onToggleBgWorker}
                    onViewLog={onViewLog}
                    onUpdateInterval={onUpdateInterval}
                  />
                )
              })}
            </div>
          </div>
        )}
        {activeSubTab === 'livestream' && <Livestream events={events} />}
      </div>
    </div>
  )
}

const styles = {
  container: {
    flex: 1,
    display: 'flex',
    overflow: 'hidden',
  },
  subTabSidebar: {
    width: 100,
    flexShrink: 0,
    borderRight: `1px solid ${theme.border}`,
    background: theme.surface,
    paddingTop: 12,
  },
  subTab: {
    padding: '8px 16px',
    fontSize: 12,
    fontWeight: 600,
    color: theme.textMuted,
    cursor: 'pointer',
    transition: 'all 0.15s',
    borderLeftWidth: 2,
    borderLeftStyle: 'solid',
    borderLeftColor: 'transparent',
  },
  subTabActive: {
    color: theme.accent,
    borderLeftColor: theme.accent,
  },
  subTabContent: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  workersContent: {
    flex: 1,
    overflowY: 'auto',
    padding: 20,
  },
  heading: {
    fontSize: 16,
    fontWeight: 600,
    color: theme.textBright,
    marginBottom: 16,
    marginTop: 0,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: 16,
  },
  card: {
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    padding: 16,
    background: theme.surface,
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    flexShrink: 0,
  },
  label: {
    fontSize: 14,
    fontWeight: 600,
    color: theme.text,
    flex: 1,
  },
  status: {
    fontSize: 11,
    fontWeight: 600,
    color: theme.textMuted,
    textTransform: 'uppercase',
  },
  lastRun: {
    fontSize: 12,
    color: theme.textMuted,
    marginBottom: 8,
  },
  details: {
    borderTop: `1px solid ${theme.border}`,
    paddingTop: 8,
  },
  detailsError: {
    borderTop: `1px solid ${theme.red}`,
    paddingTop: 8,
    background: theme.redSubtle,
    margin: '0 -16px -16px',
    padding: '8px 16px 16px',
    borderRadius: '0 0 8px 8px',
  },
  detailsErrorCompact: {
    borderTop: `1px solid ${theme.red}`,
    paddingTop: 8,
    background: theme.redSubtle,
    margin: '0 -16px 0',
    padding: '8px 16px',
  },
  detailRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 11,
    padding: '2px 0',
  },
  errorRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 11,
    padding: '2px 0',
  },
  detailKey: {
    color: theme.textMuted,
    textTransform: 'capitalize',
  },
  detailValue: {
    color: theme.text,
    fontWeight: 600,
  },
  detailKeyError: {
    color: theme.red,
    textTransform: 'capitalize',
  },
  detailValueError: {
    color: theme.red,
    fontWeight: 600,
  },
  toggleOn: {
    padding: '2px 10px',
    fontSize: 10,
    fontWeight: 600,
    border: `1px solid ${theme.green}`,
    borderRadius: 10,
    background: theme.greenSubtle,
    color: theme.green,
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  toggleOff: {
    padding: '2px 10px',
    fontSize: 10,
    fontWeight: 600,
    border: `1px solid ${theme.border}`,
    borderRadius: 10,
    background: theme.surface,
    color: theme.textMuted,
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  statusPillOk: {
    fontSize: 10,
    fontWeight: 600,
    color: theme.green,
    background: theme.greenSubtle,
    border: `1px solid ${theme.green}`,
    borderRadius: 10,
    padding: '1px 8px',
    textTransform: 'uppercase',
  },
  statusPillError: {
    fontSize: 10,
    fontWeight: 600,
    color: theme.red,
    background: theme.redSubtle,
    border: `1px solid ${theme.red}`,
    borderRadius: 10,
    padding: '1px 8px',
    textTransform: 'uppercase',
  },
  systemBadge: {
    fontSize: 10,
    fontWeight: 600,
    color: theme.textMuted,
    border: `1px solid ${theme.border}`,
    borderRadius: 10,
    padding: '1px 8px',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  cardActions: {
    display: 'flex',
    gap: 8,
    paddingTop: 8,
    borderTop: `1px solid ${theme.border}`,
    marginTop: 8,
  },
  viewLogLink: {
    fontSize: 10,
    fontWeight: 600,
    color: theme.accent,
    cursor: 'pointer',
    padding: '3px 8px',
    borderRadius: 4,
    border: `1px solid ${theme.border}`,
    background: 'transparent',
    transition: 'background 0.15s',
  },
  scheduleRow: {
    fontSize: 11,
    color: theme.textMuted,
    marginBottom: 8,
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    flexWrap: 'wrap',
  },
  scheduleText: {
    color: theme.textMuted,
  },
  nextRunText: {
    color: theme.textMuted,
  },
  editIntervalLink: {
    fontSize: 10,
    fontWeight: 600,
    color: theme.accent,
    cursor: 'pointer',
    marginLeft: 4,
  },
  intervalEditor: {
    display: 'flex',
    gap: 4,
    marginBottom: 8,
    flexWrap: 'wrap',
  },
  presetButton: {
    padding: '2px 8px',
    fontSize: 10,
    fontWeight: 600,
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    background: theme.surface,
    color: theme.textMuted,
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  presetActive: {
    padding: '2px 8px',
    fontSize: 10,
    fontWeight: 600,
    border: `1px solid ${theme.accent}`,
    borderRadius: 8,
    background: theme.accentSubtle,
    color: theme.accent,
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
}

// Pre-computed sub-tab style variants (avoids object spread in .map())
const subTabInactiveStyle = styles.subTab
const subTabActiveStyle = { ...styles.subTab, ...styles.subTabActive }
