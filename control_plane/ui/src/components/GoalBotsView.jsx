import React, { useState, useEffect } from 'react'
import { RefreshCw, Target, Play, X, Clock, CheckCircle, XCircle, AlertCircle, Loader } from 'lucide-react'
import GoalBotCard from './GoalBotCard'

// Format seconds into human-readable duration
const formatDuration = (seconds) => {
  if (!seconds) return 'N/A'
  if (seconds >= 86400) {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    return hours > 0 ? `${days}d ${hours}h` : `${days}d`
  }
  if (seconds >= 3600) {
    const hours = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`
  }
  if (seconds >= 60) {
    const mins = Math.floor(seconds / 60)
    return `${mins}m`
  }
  return `${seconds}s`
}

function GoalBotsView({
  goalBots,
  loading,
  error,
  selectedBot,
  selectedBotDetails,
  setSelectedBot,
  onRefresh,
  onFetchDetails,
  onToggle,
  onTrigger,
  onCancel,
  onFetchRuns,
  onFetchRunDetails,
  onResetState,
}) {
  const [runs, setRuns] = useState([])
  const [selectedRun, setSelectedRun] = useState(null)
  const [viewMode, setViewMode] = useState('details') // 'details' | 'runs' | 'state'

  // Fetch details when bot is selected
  useEffect(() => {
    if (selectedBot) {
      onFetchDetails(selectedBot.bot_id)
    }
  }, [selectedBot])

  // Fetch runs when viewing runs tab
  useEffect(() => {
    if (selectedBot && viewMode === 'runs') {
      loadRuns()
    }
  }, [selectedBot, viewMode])

  const loadRuns = async () => {
    if (!selectedBot) return
    const data = await onFetchRuns(selectedBot.bot_id)
    setRuns(data.runs || [])
  }

  const handleSelectRun = async (run) => {
    const details = await onFetchRunDetails(selectedBot.bot_id, run.run_id)
    setSelectedRun(details)
  }

  const getRunStatusIcon = (status) => {
    switch (status) {
      case 'completed': return <CheckCircle size={14} className="text-success" />
      case 'failed': return <XCircle size={14} className="text-error" />
      case 'running': return <Loader size={14} className="spin text-info" />
      case 'cancelled': return <X size={14} className="text-warning" />
      case 'timeout': return <AlertCircle size={14} className="text-warning" />
      default: return <Clock size={14} />
    }
  }

  if (loading) {
    return <div className="loading">Loading goals...</div>
  }

  if (error) {
    return (
      <div className="error-container">
        <p className="error">Error: {error}</p>
        <button onClick={onRefresh} className="btn btn-outline-primary">
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="content-section">
      <div className="section-header">
        <h2>Goals ({goalBots.length})</h2>
        <button onClick={onRefresh} className="btn btn-outline-secondary">
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      <div className="agents-grid">
        {goalBots.map(bot => (
          <GoalBotCard
            key={bot.bot_id}
            bot={bot}
            onClick={setSelectedBot}
          />
        ))}
      </div>

      {goalBots.length === 0 && (
        <div className="empty-state-container">
          <div className="empty-state-icon">
            <Target size={48} />
          </div>
          <h3 className="empty-state-title">No Goals</h3>
          <p className="empty-state-description">
            Goals are registered automatically from agents with goal configurations.
          </p>
        </div>
      )}

      {/* Bot Details Modal */}
      {selectedBot && (
        <div className="modal-overlay" onClick={() => setSelectedBot(null)}>
          <div className="modal-content modal-lg" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">
                <Target size={20} />
                {selectedBot.name}
                {!selectedBot.is_enabled && <span className="stat-badge disabled" style={{ marginLeft: '0.5rem' }}>Disabled</span>}
                {selectedBot.has_running_job && <span className="stat-badge running" style={{ marginLeft: '0.5rem' }}><Loader size={12} className="spin" /> Running</span>}
              </h2>
              <button className="modal-close" onClick={() => setSelectedBot(null)}>
                <X size={20} />
              </button>
            </div>

            {/* Tab Navigation */}
            <div className="modal-tabs">
              <button
                className={`tab-btn ${viewMode === 'details' ? 'active' : ''}`}
                onClick={() => setViewMode('details')}
              >
                Details
              </button>
              <button
                className={`tab-btn ${viewMode === 'runs' ? 'active' : ''}`}
                onClick={() => setViewMode('runs')}
              >
                Run History
              </button>
              <button
                className={`tab-btn ${viewMode === 'state' ? 'active' : ''}`}
                onClick={() => setViewMode('state')}
              >
                State
              </button>
            </div>

            <div className="modal-body">
              {viewMode === 'details' && selectedBotDetails && (
                <div className="details-view">
                  <div className="detail-section">
                    <h4>Configuration</h4>
                    <div className="detail-grid">
                      <div className="detail-item">
                        <label>Agent</label>
                        <span className="badge">{selectedBotDetails.agent_name}</span>
                      </div>
                      <div className="detail-item">
                        <label>Schedule</label>
                        <span>{selectedBotDetails.schedule_type === 'cron'
                          ? selectedBotDetails.schedule_config?.cron_expression
                          : formatDuration(selectedBotDetails.schedule_config?.interval_seconds || 3600)
                        }</span>
                      </div>
                      <div className="detail-item">
                        <label>Max Runtime</label>
                        <span>{formatDuration(selectedBotDetails.max_runtime_seconds)}</span>
                      </div>
                      <div className="detail-item">
                        <label>Max Iterations</label>
                        <span>{selectedBotDetails.max_iterations}</span>
                      </div>
                    </div>
                  </div>

                  {selectedBotDetails.tools && selectedBotDetails.tools.length > 0 && (
                    <div className="detail-section">
                      <h4>Tools</h4>
                      <div className="tags">
                        {selectedBotDetails.tools.map(tool => (
                          <span key={tool} className="badge">{tool}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="detail-section">
                    <h4>Run Statistics</h4>
                    <div className="detail-grid">
                      <div className="detail-item">
                        <label>Total Runs</label>
                        <span>{selectedBotDetails.total_runs || 0}</span>
                      </div>
                      <div className="detail-item">
                        <label>Last Run</label>
                        <span>
                          {selectedBotDetails.recent_runs && selectedBotDetails.recent_runs.length > 0
                            ? new Date(selectedBotDetails.recent_runs[0].started_at).toLocaleString()
                            : 'Never'}
                        </span>
                      </div>
                      {selectedBotDetails.recent_runs && selectedBotDetails.recent_runs.length > 0 && (
                        <>
                          <div className="detail-item">
                            <label>Last Status</label>
                            <span className={`status-${selectedBotDetails.recent_runs[0].status}`}>
                              {selectedBotDetails.recent_runs[0].status}
                            </span>
                          </div>
                          {selectedBotDetails.recent_runs[0].duration_seconds && (
                            <div className="detail-item">
                              <label>Last Duration</label>
                              <span>{formatDuration(selectedBotDetails.recent_runs[0].duration_seconds)}</span>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {viewMode === 'runs' && (
                <div className="runs-view">
                  {runs.length === 0 ? (
                    <div className="empty-state small">
                      <p>No runs yet</p>
                    </div>
                  ) : (
                    <div className="runs-table">
                      <table>
                        <thead>
                          <tr>
                            <th>Status</th>
                            <th>Started</th>
                            <th>Duration</th>
                            <th>Iterations</th>
                            <th>Triggered By</th>
                          </tr>
                        </thead>
                        <tbody>
                          {runs.map(run => (
                            <tr key={run.run_id} onClick={() => handleSelectRun(run)} className="clickable">
                              <td>
                                <span className={`status-badge ${run.status}`}>
                                  {getRunStatusIcon(run.status)} {run.status}
                                </span>
                              </td>
                              <td>{run.started_at ? new Date(run.started_at).toLocaleString() : '-'}</td>
                              <td>{run.duration_seconds ? `${run.duration_seconds}s` : '-'}</td>
                              <td>{run.iterations_used}</td>
                              <td>{run.triggered_by}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {selectedRun && (
                    <div className="run-details-panel">
                      <h4>Run Details</h4>
                      {selectedRun.final_outcome && (
                        <div className="detail-section">
                          <label>Outcome</label>
                          <pre className="code-block">{selectedRun.final_outcome}</pre>
                        </div>
                      )}
                      {selectedRun.error_message && (
                        <div className="detail-section error">
                          <label>Error</label>
                          <pre className="code-block error">{selectedRun.error_message}</pre>
                        </div>
                      )}
                      {selectedRun.logs && selectedRun.logs.length > 0 && (
                        <div className="detail-section">
                          <label>Milestones</label>
                          <div className="logs-timeline">
                            {selectedRun.logs.map((log, idx) => (
                              <div key={idx} className={`log-entry ${log.milestone_type}`}>
                                <span className="log-type">{log.milestone_type}</span>
                                <span className="log-name">{log.milestone_name}</span>
                                <span className="log-time">{new Date(log.logged_at).toLocaleTimeString()}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {viewMode === 'state' && selectedBotDetails && (
                <div className="state-view">
                  {selectedBotDetails.state ? (
                    <>
                      <div className="state-header">
                        <span>Version: {selectedBotDetails.state.state_version}</span>
                        <span>Last updated: {selectedBotDetails.state.last_updated_at ? new Date(selectedBotDetails.state.last_updated_at).toLocaleString() : 'Never'}</span>
                        <button className="btn btn-danger btn-sm" onClick={() => onResetState(selectedBot.bot_id)}>
                          Reset State
                        </button>
                      </div>
                      <pre className="code-block">
                        {JSON.stringify(selectedBotDetails.state.state || {}, null, 2)}
                      </pre>
                    </>
                  ) : (
                    <div className="empty-state small">
                      <p>No persistent state saved yet</p>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="modal-footer">
              <div className="footer-right" style={{ marginLeft: 'auto' }}>
                {selectedBot.has_running_job ? (
                  <button className="btn btn-danger" onClick={() => onCancel(selectedBot.bot_id)}>
                    <X size={16} /> Cancel Run
                  </button>
                ) : (
                  <button className="btn btn-success" onClick={() => onTrigger(selectedBot.bot_id)}>
                    <Play size={16} /> Run Now
                  </button>
                )}
                <button
                  className={`btn ${selectedBot.is_enabled ? 'btn-outline-danger' : 'btn-outline-success'}`}
                  onClick={() => onToggle(selectedBot.bot_id)}
                >
                  {selectedBot.is_enabled ? 'Disable' : 'Enable'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default GoalBotsView
