import React, { useState, useEffect } from 'react'
import { Activity, Server, Database, Zap, Clock, Users } from 'lucide-react'
import StatusCard from './components/StatusCard'
import MetricsCard from './components/MetricsCard'
import './App.css'

function App() {
  const [healthData, setHealthData] = useState(null)
  const [metricsData, setMetricsData] = useState(null)
  const [readyData, setReadyData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(null)

  const fetchData = async () => {
    try {
      setLoading(true)

      // Fetch all endpoints in parallel
      const [healthResponse, metricsResponse, readyResponse] = await Promise.all([
        fetch('/api/health').then(r => r.json()),
        fetch('/api/metrics').then(r => r.json()),
        fetch('/api/ready').then(r => r.json())
      ])

      setHealthData(healthResponse)
      setMetricsData(metricsResponse)
      setReadyData(readyResponse)
      setLastUpdate(new Date())
    } catch (error) {
      console.error('Error fetching data:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000) // Update every 10 seconds
    return () => clearInterval(interval)
  }, [])

  if (loading && !healthData) {
    return (
      <div className="loading">
        <Activity className="loading-icon" size={32} />
        <p>Loading health dashboard...</p>
      </div>
    )
  }

  const uptime = healthData?.uptime_seconds || 0
  const uptimeFormatted = formatUptime(uptime)
  const overallStatus = readyData?.status === 'ready' ? 'healthy' : 'unhealthy'

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <div className="header-title">
            <Activity className="header-icon" size={28} />
            <h1>AI Slack Bot Health Dashboard</h1>
          </div>
          <div className="header-info">
            <span className={`status-badge ${overallStatus}`}>
              {overallStatus === 'healthy' ? '🟢 Healthy' : '🔴 Issues Detected'}
            </span>
            <span className="last-update">
              Last updated: {lastUpdate?.toLocaleTimeString()}
            </span>
          </div>
        </div>
      </header>

      <main className="main">
        <div className="dashboard-grid">
          {/* System Status */}
          <div className="grid-section">
            <h2><Server size={20} /> System Status</h2>
            <div className="cards-row">
              <StatusCard
                title="Application"
                status={healthData?.status || 'unknown'}
                details={`Uptime: ${uptimeFormatted}`}
                icon={<Activity size={20} />}
              />
              <StatusCard
                title="LLM API"
                status={readyData?.checks?.llm_api?.status || 'unknown'}
                details={`${readyData?.checks?.llm_api?.provider || 'Unknown'} - ${readyData?.checks?.llm_api?.model || 'Unknown'}`}
                icon={<Zap size={20} />}
              />
            </div>
          </div>

          {/* Service Status */}
          <div className="grid-section">
            <h2><Database size={20} /> Services</h2>
            <div className="cards-row">
              <StatusCard
                title="Cache"
                status={readyData?.checks?.cache?.status || 'unknown'}
                details={
                  readyData?.checks?.cache?.status === 'healthy'
                    ? `${readyData.checks.cache.cached_conversations || 0} conversations • ${readyData.checks.cache.memory_used || 'N/A'} memory`
                    : readyData?.checks?.cache?.message || readyData?.checks?.cache?.error || 'Not configured'
                }
                icon={<Database size={20} />}
              />
              <StatusCard
                title="Langfuse"
                status={readyData?.checks?.langfuse?.status || 'unknown'}
                details={
                  readyData?.checks?.langfuse?.status === 'healthy'
                    ? `Observability enabled • ${readyData.checks.langfuse.host || 'cloud.langfuse.com'}`
                    : readyData?.checks?.langfuse?.status === 'unhealthy'
                    ? `${readyData.checks.langfuse.message || 'Configuration error'}`
                    : `${readyData.checks.langfuse.message || 'Disabled'}`
                }
                icon={<Activity size={20} />}
              />
              <StatusCard
                title="Metrics"
                status={readyData?.checks?.metrics?.status || 'unknown'}
                details={
                  readyData?.checks?.metrics?.status === 'healthy'
                    ? `Prometheus enabled • ${readyData.checks.metrics.active_conversations || 0} active conversations`
                    : readyData?.checks?.metrics?.message || 'Disabled'
                }
                icon={<Activity size={20} />}
              />
            </div>
          </div>

          {/* Metrics */}
          <div className="grid-section">
            <h2><Users size={20} /> Application Metrics</h2>
            <div className="cards-row">
              <MetricsCard
                title="Cache Performance"
                value={metricsData?.cache?.memory_used || 'N/A'}
                label="Memory Used"
                icon={<Database size={20} />}
              />
              <MetricsCard
                title="Active Conversations"
                value={metricsData?.active_conversations?.total || metricsData?.cache?.cached_conversations || '0'}
                label={
                  metricsData?.active_conversations?.total
                    ? `${metricsData.active_conversations.tracked_by_metrics || 0} tracked, ${metricsData.active_conversations.cached_conversations || 0} cached`
                    : 'Total Active'
                }
                icon={<Users size={20} />}
              />
              <MetricsCard
                title="Uptime"
                value={uptimeFormatted}
                label="System Uptime"
                icon={<Clock size={20} />}
              />
            </div>
          </div>

          {/* Configuration */}
          <div className="grid-section">
            <h2>Configuration Status</h2>
            <StatusCard
              title="Environment Variables"
              status={readyData?.checks?.configuration?.status || 'unknown'}
              details={readyData?.checks?.configuration?.missing_variables === 'none' ?
                'All required variables present' :
                `Missing: ${readyData?.checks?.configuration?.missing_variables}`
              }
              icon={<Server size={20} />}
              fullWidth
            />
          </div>

          {/* API Endpoints */}
          {readyData?.checks?.metrics?.endpoints && (
            <div className="grid-section">
              <h2>API Endpoints</h2>
              <div className="api-links">
                <a
                  href={readyData.checks.metrics.endpoints.metrics_json}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="api-link"
                >
                  📊 Metrics (JSON)
                </a>
                <a
                  href={readyData.checks.metrics.endpoints.prometheus}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="api-link"
                >
                  📈 Prometheus Metrics
                </a>
                <a
                  href="/api/health"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="api-link"
                >
                  💚 Health Check
                </a>
                <a
                  href="/api/ready"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="api-link"
                >
                  ✅ Readiness Check
                </a>
              </div>
            </div>
          )}
        </div>
      </main>

      <footer className="footer">
        <p>AI Slack Bot v{healthData?.version || '1.0.0'} • Auto-refresh every 10 seconds</p>
        <button onClick={fetchData} className="refresh-button">
          Refresh Now
        </button>
      </footer>
    </div>
  )
}

function formatUptime(seconds) {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)

  if (days > 0) return `${days}d ${hours}h ${minutes}m`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

export default App
