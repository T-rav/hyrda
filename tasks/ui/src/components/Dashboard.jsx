import React, { useState, useEffect, useCallback } from 'react'
import {
  LayoutDashboard,
  ListChecks,
  PlayCircle,
  PauseCircle,
  Clock,
  Server,
  History,
  ArrowRight,
  ArrowUp,
  Play,
  Pause,
  RefreshCw
} from 'lucide-react'
import StatCard from './StatCard'
import TasksTable from './TasksTable'
import { useTasksData } from '../hooks/useTasksData'

function Dashboard({ onError, setLoading }) {
  const [showAllRuns, setShowAllRuns] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const recordsPerPage = 100

  const {
    tasksData,
    taskRunsData,
    taskRunsTotal,
    ragMetrics,
    loading,
    error,
    refreshData,
    loadTaskRuns
  } = useTasksData()

  // Update refresh function signature to accept per_page
  const handleRefresh = useCallback(() => {
    refreshData(currentPage, recordsPerPage)
  }, [refreshData, currentPage, recordsPerPage])

  // Handle errors
  useEffect(() => {
    if (error) {
      onError(error)
    }
  }, [error, onError])

  // Handle loading state
  useEffect(() => {
    setLoading(loading)
  }, [loading, setLoading])

  // Auto-refresh functionality
  useEffect(() => {
    let interval
    if (autoRefresh) {
      interval = setInterval(() => {
        refreshData(currentPage, recordsPerPage)
      }, 5000)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [autoRefresh, refreshData, currentPage, recordsPerPage])

  // Initial load - fetch first page with correct page size
  useEffect(() => {
    refreshData(1, recordsPerPage)
  }, [refreshData, recordsPerPage])

  const toggleAutoRefresh = () => {
    setAutoRefresh(!autoRefresh)
  }

  const toggleShowAll = () => {
    setShowAllRuns(!showAllRuns)
    setCurrentPage(1)
  }

  // Handle page change - fetch new data from API
  const handlePageChange = async (newPage) => {
    setCurrentPage(newPage)
    await loadTaskRuns(newPage, recordsPerPage)
  }

  // Calculate statistics
  const totalTasks = tasksData.length
  const runningTasks = tasksData.filter(job => job.next_run_time).length
  const pausedTasks = tasksData.filter(job => !job.next_run_time).length

  // Find next run time
  const nextRuns = tasksData
    .filter(job => job.next_run_time)
    .map(job => new Date(job.next_run_time))
    .sort((a, b) => a - b)

  const nextRun = nextRuns.length > 0 ? nextRuns[0] : null
  const nextRunText = nextRun ? (() => {
    const now = new Date()
    const diff = nextRun - now
    const minutes = Math.floor(diff / 60000)
    return minutes > 0 ? `${minutes}m` : 'Now'
  })() : 'None'

  // Calculate scheduler stats
  const totalRuns = taskRunsTotal || taskRunsData.length

  // Calculate RAG query stats
  const totalQueries = ragMetrics.total_queries || 0
  const queriesWithNoDocuments = totalQueries > 0 ? Math.round((totalQueries * (ragMetrics.miss_rate || 0)) / 100) : 0

  return (
    <div className="dashboard">
      {/* Dashboard Header */}
      <div className="glass-card mb-4">
        <div className="card-header">
          <div className="header-title">
            <LayoutDashboard size={24} />
            <h2>Dashboard</h2>
          </div>
          <div className="header-actions">
            <button
              className={`btn ${autoRefresh ? 'btn-primary' : 'btn-outline-primary'} me-2`}
              onClick={toggleAutoRefresh}
            >
              {autoRefresh ? <Pause size={16} /> : <Play size={16} />}
              {autoRefresh ? 'Stop Auto-refresh' : 'Auto-refresh'}
            </button>
            <button
              className="btn btn-outline-secondary"
              onClick={handleRefresh}
              disabled={loading}
            >
              <RefreshCw size={16} className={loading ? 'spinning' : ''} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="stats-grid mb-4">
        <StatCard
          title="Total Tasks"
          value={totalTasks}
          icon={<ListChecks size={24} />}
          variant="primary"
        />
        <StatCard
          title="Active Tasks"
          value={runningTasks}
          icon={<PlayCircle size={24} />}
          variant="success"
        />
        <StatCard
          title="Paused Tasks"
          value={pausedTasks}
          icon={<PauseCircle size={24} />}
          variant="warning"
        />
        <StatCard
          title="Next Run"
          value={nextRunText}
          icon={<Clock size={24} />}
          variant="info"
        />
      </div>

      {/* Scheduler Status */}
      <div className="glass-card mb-4">
        <div className="card-header">
          <div className="header-title">
            <Server size={20} />
            <h3>Scheduler Status</h3>
          </div>
        </div>
        <div className="card-body">
          <div className="scheduler-stats">
            <div className="stat-item">
              <strong>Total Runs:</strong>
              <span className="badge bg-info ms-2">{totalRuns}</span>
            </div>
            <div className="stat-item">
              <strong>Queries with No Documents:</strong>
              <span className={`badge ms-2 ${
                queriesWithNoDocuments === 0 ? 'bg-success' :
                queriesWithNoDocuments <= 5 ? 'bg-warning' :
                'bg-danger'
              }`}>
                {queriesWithNoDocuments}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Runs */}
      <div className="glass-card">
        <div className="card-header">
          <div className="header-title">
            <History size={20} />
            <h3>Recent Runs</h3>
          </div>
          <button
            className={`btn btn-sm ${showAllRuns ? 'btn-primary' : 'btn-outline-primary'}`}
            onClick={toggleShowAll}
          >
            {showAllRuns ? (
              <>Show Recent <ArrowUp size={16} /></>
            ) : (
              <>View All <ArrowRight size={16} /></>
            )}
          </button>
        </div>
        <TasksTable
          taskRuns={taskRunsData}
          showAll={showAllRuns}
          currentPage={currentPage}
          recordsPerPage={recordsPerPage}
          onPageChange={handlePageChange}
          total={taskRunsTotal}
        />
      </div>
    </div>
  )
}

export default Dashboard
