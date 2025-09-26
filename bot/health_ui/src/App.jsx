import React, { useState, useEffect } from 'react'
import { Activity, Server, Database, Zap, Clock, Search, CheckCircle, AlertCircle, XCircle } from 'lucide-react'
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


            {/* Infrastructure Services */}
            <InfrastructureServices ready={ready} metrics={metrics} />

            {/* RAG Metrics */}
            <RAGMetricsSection ready={ready} metrics={metrics} />

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

// Infrastructure Services Component
function InfrastructureServices({ ready, metrics }) {
  const [services, setServices] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchServices = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/services/health')
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const data = await response.json()
      setServices(data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchServices()
    const interval = setInterval(fetchServices, 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
  }, [])

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle size={16} style={{ color: '#10b981' }} />
      case 'unhealthy':
        return <AlertCircle size={16} style={{ color: '#f59e0b' }} />
      case 'error':
        return <XCircle size={16} style={{ color: '#ef4444' }} />
      default:
        return <AlertCircle size={16} style={{ color: '#6b7280' }} />
    }
  }

  const getServiceIcon = (name) => {
    if (name.includes('Database') || name.includes('MySQL')) {
      return <Database size={18} />
    } else if (name.includes('Elasticsearch')) {
      return <Search size={18} />
    } else {
      return <Server size={18} />
    }
  }

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'healthy':
        return 'status-badge healthy'
      case 'unhealthy':
        return 'status-badge unhealthy'
      case 'error':
        return 'status-badge error'
      default:
        return 'status-badge unknown'
    }
  }

  if (loading && !services) {
    return (
      <div className="grid-section">
        <h2><Server size={20} /> Infrastructure</h2>
        <div className="loading-text">Loading services...</div>
      </div>
    )
  }

  if (error && !services) {
    return (
      <div className="grid-section">
        <h2><Server size={20} /> Infrastructure</h2>
        <div className="error-text">Error loading services: {error}</div>
      </div>
    )
  }

  return (
    <div className="grid-section">
      <h2><Server size={20} /> Infrastructure</h2>
      <div className="cards-row">
        {services?.services && Object.entries(services.services).map(([key, service]) => (
          <div key={key} className="service-card">
            <div className="service-header">
              <div className="service-info">
                {getServiceIcon(service.name)}
                <span className="service-name">{service.name}</span>
              </div>
              <div className="service-status">
                {getStatusIcon(service.status)}
                <span className={getStatusBadgeClass(service.status)}>
                  {service.status}
                </span>
              </div>
            </div>
            {service.details && (
              <div className="service-details">
                {Object.entries(service.details).map(([detailKey, value]) => (
                  <div key={detailKey} className="detail-item">
                    <span className="detail-key">{detailKey.replace(/_/g, ' ')}:</span>
                    <span className="detail-value">
                      {typeof value === 'boolean'
                        ? (value ? 'Yes' : 'No')
                        : Array.isArray(value)
                          ? value.join(', ')
                          : value}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Application Services Row */}
      <div className="cards-row" style={{ marginTop: '1rem' }}>
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
      </div>
    </div>
  )
}

// RAG Metrics Component
function RAGMetricsSection({ ready }) {
  const ragData = ready?.checks?.rag

  if (!ragData || ragData.status === 'disabled') {
    return null
  }

  const formatPercentage = (value) => {
    if (typeof value === 'number') {
      return `${value.toFixed(1)}%`
    }
    return 'N/A'
  }

  const formatNumber = (value) => {
    if (typeof value === 'number') {
      return value.toLocaleString()
    }
    return 'N/A'
  }

  // const getStatusColor = (successRate) => {
  //   if (typeof successRate !== 'number') return '#6b7280'
  //   if (successRate >= 80) return '#10b981' // green
  //   if (successRate >= 60) return '#f59e0b' // yellow
  //   return '#ef4444' // red
  // }

  return (
    <div className="grid-section">
      <h2><Search size={20} /> RAG Performance Metrics</h2>
      <div className="cards-row">
        <MetricsCard
          title="Cache Hit Rate"
          value={formatPercentage(ragData.hit_rate)}
          label="Documents found in cache"
          icon={<Database size={20} />}
          status={ragData.hit_rate >= 70 ? 'healthy' : ragData.hit_rate >= 40 ? 'warning' : 'error'}
        />
        <MetricsCard
          title="Avg Chunks/Query"
          value={typeof ragData.avg_chunks === 'number' ? ragData.avg_chunks.toFixed(1) : 'N/A'}
          label="Documents retrieved per query"
          icon={<Search size={20} />}
          status="info"
        />
        <MetricsCard
          title="Success Rate"
          value={formatPercentage(ragData.success_rate)}
          label="Successful retrievals"
          icon={<CheckCircle size={20} />}
          status={ragData.success_rate >= 80 ? 'healthy' : ragData.success_rate >= 60 ? 'warning' : 'error'}
        />
        <MetricsCard
          title="Total Queries"
          value={formatNumber(ragData.total_queries)}
          label="Since last restart"
          icon={<Activity size={20} />}
          status="info"
        />
      </div>

      {ragData.documents_used > 0 && (
        <div className="rag-stats-detail">
          <div className="stat-detail-item">
            <span className="stat-detail-label">Documents Used:</span>
            <span className="stat-detail-value">{formatNumber(ragData.documents_used)}</span>
          </div>
          <div className="stat-detail-item">
            <span className="stat-detail-label">Miss Rate:</span>
            <span className="stat-detail-value">{formatPercentage(ragData.miss_rate)}</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
