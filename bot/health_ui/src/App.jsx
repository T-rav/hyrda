import React from 'react'
import { Activity, Server, Database, Zap, Clock } from 'lucide-react'
import ErrorBoundary from './components/ErrorBoundary'
import LoadingSpinner from './components/LoadingSpinner'
import ErrorMessage from './components/ErrorMessage'
import StatusCard from './components/StatusCard'
import MetricsCard from './components/MetricsCard'
import ServiceCard from './components/ServiceCard'
import { useHealthData } from './hooks/useHealthData'
import { formatUptime, getOverallStatus } from './utils/statusHelpers'
import './App.css'

function App() {
  const { health, metrics, ready, loading, error, lastUpdate, refetch } = useHealthData()

  if (loading && !health) {
    return <LoadingSpinner />
  }

  if (error && !health) {
    return (
      <div className="app">
        <ErrorMessage error={error} onRetry={refetch} />
      </div>
    )
  }

  const uptime = health?.uptime_seconds || 0
  const uptimeFormatted = formatUptime(uptime)
  const overallStatus = getOverallStatus(ready)

  return (
    <ErrorBoundary>
      <div className="app">
        <header className="header">
          <div className="header-content">
            <div className="header-title">
              <Activity className="header-icon" size={28} />
              <h1>InsightMesh Health Dashboard</h1>
            </div>
            <div className="header-info">
              <span className={`status-badge ${overallStatus}`}>
                {overallStatus === 'healthy' ? '🟢 Healthy' : overallStatus === 'unhealthy' ? '🔴 Issues Detected' : '⚪ Unknown'}
              </span>
              <span className="last-update">
                Last updated: {lastUpdate?.toLocaleTimeString() || 'Never'}
              </span>
            </div>
          </div>
        </header>

        <main className="main">
          {error && <ErrorMessage error={error} onRetry={refetch} />}

          <div className="dashboard-grid">
            {/* System Status */}
            <div className="grid-section">
              <h2><Server size={20} /> System Status</h2>
              <div className="cards-row">
                <StatusCard
                  title="Application"
                  status={health?.status || 'unknown'}
                  details={`Version: ${health?.version || '1.0.0'}`}
                  icon={<Activity size={20} />}
                />
                <StatusCard
                  title="LLM API"
                  status={ready?.checks?.llm_api?.status || 'unknown'}
                  details={`${ready?.checks?.llm_api?.provider || 'Unknown'} - ${ready?.checks?.llm_api?.model || 'Unknown'}`}
                  icon={<Zap size={20} />}
                />
                <MetricsCard
                  title="System Uptime"
                  value={uptimeFormatted}
                  label={`Last updated: ${lastUpdate?.toLocaleTimeString() || 'Never'}`}
                  icon={<Clock size={20} />}
                />
              </div>
            </div>

            {/* Services */}
            <div className="grid-section">
              <h2><Database size={20} /> Services</h2>
              <div className="cards-row">
                <ServiceCard
                  service="cache"
                  title="Cache"
                  icon={<Database size={20} />}
                  serviceData={ready?.checks?.cache}
                  metricsData={metrics}
                />
                <ServiceCard
                  service="langfuse"
                  title="Langfuse"
                  icon={<Activity size={20} />}
                  serviceData={ready?.checks?.langfuse}
                  metricsData={metrics}
                />
                <ServiceCard
                  service="metrics"
                  title="Metrics"
                  icon={<Activity size={20} />}
                  serviceData={ready?.checks?.metrics}
                  metricsData={metrics}
                />
              </div>
            </div>


            {/* API Endpoints */}
            {ready?.checks?.metrics?.endpoints && (
              <div className="grid-section">
                <h2>API Endpoints</h2>
                <div className="api-links">
                  <a
                    href={ready.checks.metrics.endpoints.metrics_json}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="api-link"
                  >
                    📊 Metrics (JSON)
                  </a>
                  <a
                    href={ready.checks.metrics.endpoints.prometheus}
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
                  <a
                    href="http://localhost:5001"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="api-link"
                  >
                    📅 Task Scheduler
                  </a>
                  <a
                    href="http://localhost:8081"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="api-link"
                  >
                    🗄️ Database Admin
                  </a>
                </div>
              </div>
            )}
          </div>
        </main>

        <footer className="footer">
          <p>InsightMesh v{health?.version || '1.0.0'} • Auto-refresh every 10 seconds</p>
          <button onClick={refetch} className="refresh-button" disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh Now'}
          </button>
        </footer>
      </div>
    </ErrorBoundary>
  )
}

export default App
