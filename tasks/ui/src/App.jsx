import React, { useState } from 'react'
import { CalendarClock, LayoutDashboard, ListChecks, Activity, ArrowRight, ArrowUp, ChevronLeft, ChevronRight, Play, Pause, Trash2, RefreshCw, PlayCircle, Eye, Plus, X, Key } from 'lucide-react'
import CredentialsManager from './components/CredentialsManager'
import CreateTaskModal from './components/CreateTaskModal'
import ViewTaskModal from './components/ViewTaskModal'
import './App.css'
import { logError } from './utils/logger'

// Custom hook for managing document title
function useDocumentTitle(title) {
  React.useEffect(() => {
    const previousTitle = document.title
    document.title = title
    return () => {
      document.title = previousTitle
    }
  }, [title])
}

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [notification, setNotification] = useState(null)

  // Use the custom hook to set document title
  useDocumentTitle('InsightMesh - Tasks Dashboard')

  const handleTabChange = (tab) => {
    setActiveTab(tab)
  }

  const showNotification = (message, type = 'success') => {
    setNotification({ message, type })
    setTimeout(() => setNotification(null), 3000)
  }

  return (
    <div className="app">
      {/* Header - Match Health UI style */}
      <header className="header">
        <div className="header-content">
          <div className="header-title">
            <CalendarClock className="header-icon" size={28} />
            <h1>InsightMesh Tasks</h1>
          </div>
          <nav className="header-nav">
            <button
              className={`nav-link ${activeTab === 'dashboard' ? 'active' : ''}`}
              onClick={() => handleTabChange('dashboard')}
            >
              <LayoutDashboard size={20} />
              Dashboard
            </button>
            <button
              className={`nav-link ${activeTab === 'tasks' ? 'active' : ''}`}
              onClick={() => handleTabChange('tasks')}
            >
              <ListChecks size={20} />
              Tasks
            </button>
            <button
              className={`nav-link ${activeTab === 'credentials' ? 'active' : ''}`}
              onClick={() => handleTabChange('credentials')}
            >
              <Key size={20} />
              Credentials
            </button>
            <a
              href="http://localhost:8080/ui"
              target="_blank"
              rel="noopener noreferrer"
              className="nav-link external"
            >
              <Activity size={20} />
              Health
            </a>
            <div className="nav-divider"></div>
          </nav>
        </div>
      </header>

      <main className="main-content">
        {activeTab === 'dashboard' && <DashboardContent showNotification={showNotification} />}
        {activeTab === 'tasks' && <TasksContent showNotification={showNotification} />}
        {activeTab === 'credentials' && <CredentialsManager />}
      </main>

      <footer className="footer">
        <p>InsightMesh Tasks v1.0.0</p>
      </footer>

      {/* Notification */}
      {notification && (
        <div className={`notification notification-${notification.type}`}>
          <div className="notification-content">
            <span>{notification.message}</span>
            <button
              className="notification-close"
              onClick={() => setNotification(null)}
            >
              <X size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// Dashboard Component with Real API Data
function DashboardContent() {
  const [loading, setLoading] = useState(false)
  const [showAllRuns, setShowAllRuns] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const recordsPerPage = 20
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(null)
  const [data, setData] = useState({
    jobs: [],
    taskRuns: [],
    scheduler: {}
  })

  const loadData = async () => {
    setLoading(true)
    try {
      const [jobsRes, runsRes, schedulerRes] = await Promise.all([
        fetch('/api/jobs', { credentials: 'include' }).then(r => r.json()),
        fetch('/api/task-runs', { credentials: 'include' }).then(r => r.json()),
        fetch('/api/scheduler/info', { credentials: 'include' }).then(r => r.json())
      ])

      setData({
        jobs: jobsRes.jobs || [],
        taskRuns: runsRes.task_runs || [],
        scheduler: schedulerRes
      })
    } catch (error) {
      logError('Error loading data:', error)
    } finally {
      setLoading(false)
    }
  }

  // Load data on component mount
  React.useEffect(() => {
    loadData()
  }, [])

  // Auto-refresh effect
  React.useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        loadData()
      }, 10000) // 10 seconds
      setRefreshInterval(interval)

      return () => {
        clearInterval(interval)
      }
    } else if (refreshInterval) {
      clearInterval(refreshInterval)
      setRefreshInterval(null)
    }
  }, [autoRefresh, refreshInterval])

  const toggleAutoRefresh = () => {
    setAutoRefresh(!autoRefresh)
  }

  // Calculate statistics
  const totalTasks = data.jobs.length
  const activeTasks = data.jobs.filter(job => job.next_run_time).length
  const pausedTasks = data.jobs.filter(job => !job.next_run_time).length

  // Calculate next run
  const nextRuns = data.jobs
    .filter(job => job.next_run_time)
    .map(job => new Date(job.next_run_time))
    .sort((a, b) => a - b)

  const nextRunText = nextRuns.length > 0 ? (() => {
    const nextRun = nextRuns[0]
    const now = new Date()
    const diff = nextRun - now
    const minutes = Math.floor(diff / 60000)
    return minutes > 0 ? `${minutes}m` : 'Now'
  })() : 'None'

  // Calculate success rate
  const totalRuns = data.taskRuns.length
  const successfulRuns = data.taskRuns.filter(run => run.status === 'success').length
  const successRate = totalRuns > 0 ? Math.round((successfulRuns / totalRuns) * 100) : 0

  return (
    <div className="dashboard">
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
              <Play size={16} className="me-1" />
              {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh'}
            </button>
            <button
              className="btn btn-outline-secondary"
              onClick={loadData}
              disabled={loading}
            >
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="stats-grid mb-4">
        <StatCard title="Total Tasks" value={totalTasks} variant="primary" />
        <StatCard title="Active Tasks" value={activeTasks} variant="success" />
        <StatCard title="Paused Tasks" value={pausedTasks} variant="warning" />
        <StatCard title="Next Run" value={nextRunText} variant="info" />
      </div>

      {/* Scheduler Status */}
      <div className="glass-card mb-4">
        <div className="card-header">
          <div className="header-title">
            <h3>Scheduler Status</h3>
          </div>
        </div>
        <div className="scheduler-stats">
          <div className="stat-item">
            <strong>Total Runs:</strong>
            <span className="badge bg-info ms-2">{totalRuns}</span>
          </div>
          <div className="stat-item">
            <strong>Success Rate:</strong>
            <span className={`badge ms-2 ${
              successRate >= 90 ? 'bg-success' :
              successRate >= 70 ? 'bg-warning' :
              'bg-danger'
            }`}>
              {successRate}% ({successfulRuns}/{totalRuns})
            </span>
          </div>
        </div>
      </div>


      {/* Recent Runs */}
      <div className="glass-card">
        <div className="card-header">
          <div className="header-title">
            <h3>Recent Runs</h3>
          </div>
          <button
            className={`btn btn-sm ${showAllRuns ? 'btn-primary' : 'btn-outline-primary'}`}
            onClick={() => {
              setShowAllRuns(!showAllRuns)
              setCurrentPage(1)
            }}
          >
            {showAllRuns ? (
              <>Show Recent <ArrowUp size={16} /></>
            ) : (
              <>View All <ArrowRight size={16} /></>
            )}
          </button>
        </div>
        <RecentRunsTable
          taskRuns={data.taskRuns}
          showAllRuns={showAllRuns}
          currentPage={currentPage}
          recordsPerPage={recordsPerPage}
          onPageChange={setCurrentPage}
        />
      </div>
    </div>
  )
}

// Full Tasks Component with Management
function TasksContent({ showNotification }) {
  const [loading, setLoading] = useState(false)
  const [tasks, setTasks] = useState([])
  const [actionLoading, setActionLoading] = useState({})
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showViewModal, setShowViewModal] = useState(false)
  const [selectedTask, setSelectedTask] = useState(null)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(null)

  const loadTasks = async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/jobs', { credentials: 'include' })
      const data = await response.json()
      setTasks(data.jobs || [])
    } catch (error) {
      logError('Error loading tasks:', error)
    } finally {
      setLoading(false)
    }
  }

  // Load data on component mount
  React.useEffect(() => {
    loadTasks()
  }, [])

  // Auto-refresh effect
  React.useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        loadTasks()
      }, 10000) // 10 seconds
      setRefreshInterval(interval)

      return () => {
        clearInterval(interval)
      }
    } else if (refreshInterval) {
      clearInterval(refreshInterval)
      setRefreshInterval(null)
    }
  }, [autoRefresh, refreshInterval])

  const toggleAutoRefresh = () => {
    setAutoRefresh(!autoRefresh)
  }

  // Helper function to get clean display name
  const getTaskDisplayName = (task) => {
    if (!task) return 'Task'

    if (task.name && task.name !== task.id) {
      return task.name
    }

    // If no name or name is same as ID, try to derive a clean name from the ID
    if (task.id.includes('slack_user_import')) {
      return 'Slack User Import'
    }

    // Default fallback
    return task.name || 'Task'
  }

  const handleTaskAction = async (action, taskId) => {
    setActionLoading({ ...actionLoading, [taskId]: action })

    try {
      let response
      switch (action) {
        case 'pause':
          response = await fetch(`/api/jobs/${taskId}/pause`, { method: 'POST', credentials: 'include' })
          if (response && response.ok) {
            const task = tasks.find(t => t.id === taskId)
            const taskName = getTaskDisplayName(task)
            showNotification(`${taskName} paused successfully`, 'success')
            await loadTasks()
          } else {
            throw new Error('Failed to pause task')
          }
          break
        case 'resume':
          response = await fetch(`/api/jobs/${taskId}/resume`, { method: 'POST', credentials: 'include' })
          if (response && response.ok) {
            const task = tasks.find(t => t.id === taskId)
            const taskName = getTaskDisplayName(task)
            showNotification(`${taskName} resumed successfully`, 'success')
            await loadTasks()
          } else {
            throw new Error('Failed to resume task')
          }
          break
        case 'run-once':
          response = await fetch(`/api/jobs/${taskId}/run-once`, { method: 'POST', credentials: 'include' })
          if (response && response.ok) {
            const task = tasks.find(t => t.id === taskId)
            const taskName = getTaskDisplayName(task)
            showNotification(`${taskName} triggered successfully`, 'success')
            await loadTasks()
          } else {
            throw new Error('Failed to trigger task')
          }
          break
        case 'delete':
          const task = tasks.find(t => t.id === taskId)
          const taskName = getTaskDisplayName(task)
          if (window.confirm(`Are you sure you want to delete ${taskName}?`)) {
            response = await fetch(`/api/jobs/${taskId}`, { method: 'DELETE', credentials: 'include' })
            if (response && response.ok) {
              showNotification(`${taskName} deleted successfully`, 'success')
              await loadTasks()
            } else {
              throw new Error('Failed to delete task')
            }
          } else {
            setActionLoading({ ...actionLoading, [taskId]: null })
            return
          }
          break
        case 'view':
          // Load task details and show modal
          try {
            const taskResponse = await fetch(`/api/jobs/${taskId}`, { credentials: 'include' })
            if (taskResponse.ok) {
              const taskData = await taskResponse.json()
              setSelectedTask(taskData)
              setShowViewModal(true)
            } else {
              throw new Error('Failed to load task details')
            }
          } catch (error) {
            showNotification('Error loading task details', 'error')
          }
          setActionLoading({ ...actionLoading, [taskId]: null })
          return
        default:
          break
      }
    } catch (error) {
      logError(`Error ${action} task:`, error)
      showNotification(`Error: ${error.message}`, 'error')
    } finally {
      setActionLoading({ ...actionLoading, [taskId]: null })
    }
  }

  const formatNextRun = (nextRunTime) => {
    if (!nextRunTime) return 'Paused'

    const nextRun = new Date(nextRunTime)
    const now = new Date()
    const diff = nextRun - now

    if (diff <= 0) return 'Now'

    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (days > 0) return `${days}d ${hours % 24}h`
    if (hours > 0) return `${hours}h ${minutes % 60}m`
    return `${minutes}m`
  }

  return (
    <div className="tasks-list">
      {/* Task Management Header */}
      <div className="glass-card mb-4">
        <div className="card-header">
          <div className="header-title">
            <CalendarClock size={24} />
            <h2>Task Management</h2>
          </div>
          <div className="header-actions">
            <button
              className="btn btn-outline-success me-2"
              onClick={() => setShowCreateModal(true)}
            >
              <Plus size={16} className="me-1" />
              Create Task
            </button>
            <button
              className={`btn ${autoRefresh ? 'btn-primary' : 'btn-outline-primary'} me-2`}
              onClick={toggleAutoRefresh}
            >
              <Play size={16} className="me-1" />
              {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh'}
            </button>
            <button
              className="btn btn-outline-secondary"
              onClick={loadTasks}
              disabled={loading}
            >
              <RefreshCw size={16} />
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>
      </div>

      {/* All Tasks Table */}
      <div className="glass-card">
        <div className="card-header mb-4">
          <div className="header-title">
            <ListChecks size={24} />
            <h3>All Tasks</h3>
            <span className="badge bg-primary ms-2">{tasks.length}</span>
          </div>
        </div>

        <div className="table-container">
          {tasks.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📋</div>
              <p>No tasks scheduled</p>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>
                    <Play size={16} className="me-1" />
                    Name
                  </th>
                  <th>
                    <CalendarClock size={16} className="me-1" />
                    Trigger
                  </th>
                  <th>
                    <Activity size={16} className="me-1" />
                    Next Run
                  </th>
                  <th>
                    <CalendarClock size={16} className="me-1" />
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <TaskRow
                    key={task.id}
                    task={task}
                    onAction={handleTaskAction}
                    actionLoading={actionLoading}
                    formatNextRun={formatNextRun}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Create Task Modal */}
      {showCreateModal && (
        <CreateTaskModal
          onClose={() => setShowCreateModal(false)}
          onTaskCreated={(message) => {
            setShowCreateModal(false)
            showNotification(message || 'Task created successfully', 'success')
            loadTasks()
          }}
        />
      )}

      {/* View Task Modal */}
      {showViewModal && selectedTask && (
        <ViewTaskModal
          task={selectedTask}
          onClose={() => {
            setShowViewModal(false)
            setSelectedTask(null)
          }}
        />
      )}
    </div>
  )
}

// Task Row Component
function TaskRow({ task, onAction, actionLoading, formatNextRun }) {
  const isActive = !!task.next_run_time
  const currentAction = actionLoading[task.id]

  // Get task type from args and create user-friendly description
  const taskType = task.args && task.args.length > 0 ? task.args[0] : 'Unknown'

  // Map task types to user-friendly descriptions
  const taskTypeDescriptions = {
    'slack_user_import': 'Slack User Import',
    'metric_sync': 'Metric.ai Data Sync',
    'gdrive_ingest': 'Google Drive Ingestion',
    'youtube_ingest': 'YouTube Ingestion',
    'website_scrape': 'Website Scraping'
  }

  const taskDescription = taskTypeDescriptions[taskType] || taskType

  return (
    <tr>
      <td>
        <div>
          <strong>{task.name && task.name !== task.id ? task.name : taskDescription}</strong>
          {isActive ? (
            <span className="badge bg-success ms-2">Active</span>
          ) : (
            <span className="badge bg-warning ms-2">Paused</span>
          )}
        </div>
        <small className="text-muted">{taskDescription}</small>
      </td>
      <td>
        <span className="badge bg-secondary">
          {task.trigger || 'Unknown'}
        </span>
      </td>
      <td>
        {task.next_run_time ? formatNextRun(task.next_run_time) : 'Paused'}
      </td>
      <td>
        <div className="btn-group btn-group-sm" role="group">
          <button
            className="btn btn-outline-primary btn-sm"
            onClick={() => onAction('view', task.id)}
            disabled={currentAction === 'view'}
            title="View Details"
          >
            <Eye size={12} />
          </button>
          <button
            className={`btn ${isActive ? 'btn-outline-warning' : 'btn-outline-success'} btn-sm`}
            onClick={() => onAction(isActive ? 'pause' : 'resume', task.id)}
            disabled={currentAction === 'pause' || currentAction === 'resume'}
            title={isActive ? 'Pause' : 'Resume'}
          >
            {isActive ? <Pause size={12} /> : <Play size={12} />}
          </button>
          <button
            className="btn btn-outline-info btn-sm"
            onClick={() => onAction('run-once', task.id)}
            disabled={currentAction === 'run-once'}
            title="Run Once"
          >
            <PlayCircle size={12} />
          </button>
          <button
            className="btn btn-outline-danger btn-sm"
            onClick={() => onAction('delete', task.id)}
            disabled={currentAction === 'delete'}
            title="Delete"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </td>
    </tr>
  )
}

// Simple Stat Card Component
function StatCard({ title, value, variant = 'primary' }) {
  const variantStyles = {
    primary: 'stat-card-primary',
    success: 'stat-card-success',
    warning: 'stat-card-warning',
    info: 'stat-card-info'
  }

  const variantClass = variantStyles[variant] || variantStyles.primary

  return (
    <div className={`glass-card stat-card ${variantClass}`}>
      <div className="stat-content">
        <div className="stat-info">
          <h3 className="stat-number">{value}</h3>
          <p className="stat-label">{title}</p>
        </div>
      </div>
    </div>
  )
}


// Recent Runs Table Component with Pagination
function RecentRunsTable({ taskRuns, showAllRuns, currentPage, recordsPerPage, onPageChange }) {
  if (!taskRuns || taskRuns.length === 0) {
    return (
      <div className="table-container">
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <p>No recent runs</p>
        </div>
      </div>
    )
  }

  // Calculate displayed runs
  let displayedRuns
  if (showAllRuns) {
    const startIndex = (currentPage - 1) * recordsPerPage
    const endIndex = startIndex + recordsPerPage
    displayedRuns = taskRuns.slice(startIndex, endIndex)
  } else {
    displayedRuns = taskRuns.slice(0, 5)
  }

  // Pagination info
  const totalPages = Math.ceil(taskRuns.length / recordsPerPage)
  const startRecord = (currentPage - 1) * recordsPerPage + 1
  const endRecord = Math.min(currentPage * recordsPerPage, taskRuns.length)

  return (
    <div className="table-container">
      <table className="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Started</th>
            <th>Status</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          {displayedRuns.map((run, index) => (
            <TaskRunRow key={index} run={run} />
          ))}
        </tbody>
      </table>

      {/* Pagination Controls */}
      {showAllRuns && totalPages > 1 && (
        <div className="pagination-controls">
          <div className="pagination-info">
            <span className="text-muted">
              Showing {startRecord}-{endRecord} of {taskRuns.length} runs
            </span>
          </div>
          <nav className="pagination-nav">
            <button
              className={`btn btn-sm btn-outline-secondary ${currentPage === 1 ? 'disabled' : ''}`}
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage === 1}
            >
              <ChevronLeft size={16} />
              Previous
            </button>

            {/* Page numbers */}
            <div className="page-numbers">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                const startPage = Math.max(1, currentPage - 2)
                const pageNum = startPage + i
                if (pageNum > totalPages) return null

                return (
                  <button
                    key={pageNum}
                    className={`btn btn-sm ${
                      pageNum === currentPage ? 'btn-primary' : 'btn-outline-secondary'
                    }`}
                    onClick={() => onPageChange(pageNum)}
                  >
                    {pageNum}
                  </button>
                )
              })}
            </div>

            <button
              className={`btn btn-sm btn-outline-secondary ${
                currentPage === totalPages ? 'disabled' : ''
              }`}
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
            >
              Next
              <ChevronRight size={16} />
            </button>
          </nav>
        </div>
      )}
    </div>
  )
}

// Task Run Row Component
function TaskRunRow({ run }) {
  const statusStyles = {
    running: 'bg-primary',
    success: 'bg-success',
    failed: 'bg-danger',
    cancelled: 'bg-secondary'
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleString()
  }

  const formatDuration = (run) => {
    if (run.duration_seconds) {
      return `${run.duration_seconds.toFixed(1)}s`
    }
    return run.status === 'running' ? 'Running...' : 'N/A'
  }

  const statusClass = statusStyles[run.status] || statusStyles.cancelled

  return (
    <tr>
        <td>
          <div className="task-name">
            <strong>{run.job_name || 'Unknown Job'}</strong>
            {run.triggered_by === 'manual' && (
              <span className="badge bg-primary ms-1">MANUAL</span>
            )}
          </div>
        </td>
      <td>{formatDate(run.started_at)}</td>
      <td>
        <span className={`badge ${statusClass}`}>
          {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
        </span>
      </td>
      <td>
        <div className="task-details">
          <small className="text-muted">
            {formatDuration(run)}
            {run.records_processed && ` • ${run.records_processed} records`}
          </small>
        </div>
      </td>
    </tr>
  )
}

export default App
