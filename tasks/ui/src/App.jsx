import React, { useState } from 'react'
import { CalendarClock, LayoutDashboard, ListChecks, Activity, ArrowRight, ArrowUp, ChevronLeft, ChevronRight, Play, Pause, Trash2, RefreshCw, PlayCircle, Eye, Plus, X } from 'lucide-react'
import './App.css'

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [notification, setNotification] = useState(null)

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
            <a
              href="http://localhost:8080/ui"
              target="_blank"
              rel="noopener noreferrer"
              className="nav-link external"
            >
              <Activity size={20} />
              Health
            </a>
          </nav>
        </div>
      </header>

      <main className="main-content">
        {activeTab === 'dashboard' && <DashboardContent showNotification={showNotification} />}
        {activeTab === 'tasks' && <TasksContent showNotification={showNotification} />}
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
        fetch('/api/jobs').then(r => r.json()),
        fetch('/api/task-runs').then(r => r.json()),
        fetch('/api/scheduler/info').then(r => r.json())
      ])

      setData({
        jobs: jobsRes.jobs || [],
        taskRuns: runsRes.task_runs || [],
        scheduler: schedulerRes
      })
    } catch (error) {
      console.error('Error loading data:', error)
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
    } else if (refreshInterval) {
      clearInterval(refreshInterval)
      setRefreshInterval(null)
    }

    return () => {
      if (refreshInterval) {
        clearInterval(refreshInterval)
      }
    }
  }, [autoRefresh])

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
      const response = await fetch('/api/jobs')
      const data = await response.json()
      setTasks(data.jobs || [])
    } catch (error) {
      console.error('Error loading tasks:', error)
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
    } else if (refreshInterval) {
      clearInterval(refreshInterval)
      setRefreshInterval(null)
    }

    return () => {
      if (refreshInterval) {
        clearInterval(refreshInterval)
      }
    }
  }, [autoRefresh])

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
          response = await fetch(`/api/jobs/${taskId}/pause`, { method: 'POST' })
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
          response = await fetch(`/api/jobs/${taskId}/resume`, { method: 'POST' })
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
          response = await fetch(`/api/jobs/${taskId}/run-once`, { method: 'POST' })
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
            response = await fetch(`/api/jobs/${taskId}`, { method: 'DELETE' })
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
            const taskResponse = await fetch(`/api/jobs/${taskId}`)
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
      console.error(`Error ${action} task:`, error)
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

  // Clean up the task name display
  const getDisplayName = (task) => {
    if (task.name && task.name !== task.id) {
      return task.name
    }

    // If no name or name is same as ID, try to derive a clean name from the ID
    if (task.id.includes('slack_user_import')) {
      return 'Slack User Import'
    }

    // Default fallback
    return task.name || 'Unnamed Task'
  }

  return (
    <tr>
      <td>
        <div>
          <strong>{getDisplayName(task)}</strong>
          {isActive ? (
            <span className="badge bg-success ms-2">Active</span>
          ) : (
            <span className="badge bg-warning ms-2">Paused</span>
          )}
        </div>
        <small className="text-muted">{task.id}</small>
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

// Create Task Modal Component
function CreateTaskModal({ onClose, onTaskCreated }) {
  const [taskType, setTaskType] = useState('')
  const [taskName, setTaskName] = useState('')
  const [triggerType, setTriggerType] = useState('interval')
  const [hours, setHours] = useState('1')
  const [minutes, setMinutes] = useState('0')
  const [seconds, setSeconds] = useState('0')
  const [cronExpression, setCronExpression] = useState('0 0 * * *')
  const [runDate, setRunDate] = useState('')
  const [taskTypes, setTaskTypes] = useState([])
  const [loading, setLoading] = useState(false)

  // Load task types on component mount
  React.useEffect(() => {
    const loadTaskTypes = async () => {
      try {
        const response = await fetch('/api/job-types')
        const data = await response.json()
        setTaskTypes(data.job_types || [])
      } catch (error) {
        console.error('Error loading task types:', error)
      }
    }
    loadTaskTypes()
  }, [])

  // Helper function to extract parameter values from form elements
  const getParameterValue = (element, param) => {
    if (element.multiple) {
      // Multi-select dropdown
      const selectedValues = Array.from(element.selectedOptions).map(option => option.value)
      return selectedValues.length > 0 ? selectedValues : null
    } else if (element.tagName === 'SELECT') {
      // Single select dropdown
      if (element.value) {
        // Convert boolean strings to actual booleans
        if (element.value === 'true') {
          return true
        } else if (element.value === 'false') {
          return false
        } else {
          return element.value
        }
      }
      return null
    } else if (element.tagName === 'TEXTAREA') {
      // Textarea - try to parse as JSON for metadata fields
      if (element.value.trim()) {
        if (param === 'metadata') {
          try {
            return JSON.parse(element.value.trim())
          } catch (e) {
            // If not valid JSON, return as string
            return element.value.trim()
          }
        }
        return element.value.trim()
      }
      return null
    } else if (element.type === 'number') {
      // Number input
      return element.value ? parseInt(element.value) : null
    } else {
      // Regular text input
      return element.value.trim() || null
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!taskType || !taskName) {
      alert('Please fill in all required fields')
      return
    }

    setLoading(true)
    try {
      const selectedTaskType = taskTypes.find(tt => tt.type === taskType)
      const parameters = {}

      // Collect required parameters
      if (selectedTaskType?.required_params) {
        for (const param of selectedTaskType.required_params) {
          const element = document.getElementById(`param_${param}`)
          if (element) {
            const value = getParameterValue(element, param)
            if (value !== null && value !== '') {
              parameters[param] = value
            } else if (element.required) {
              alert(`Required parameter '${param}' is missing`)
              setLoading(false)
              return
            }
          }
        }
      }

      // Collect optional parameters
      if (selectedTaskType?.optional_params) {
        for (const param of selectedTaskType.optional_params) {
          const element = document.getElementById(`param_${param}`)
          if (element) {
            const value = getParameterValue(element, param)
            if (value !== null && value !== '') {
              parameters[param] = value
            }
          }
        }
      }

      const taskData = {
        job_type: taskType,
        name: taskName,
        schedule: {
          trigger: triggerType,
          hours: parseInt(hours) || 0,
          minutes: parseInt(minutes) || 0,
          seconds: parseInt(seconds) || 0
        },
        parameters: parameters
      }

      const response = await fetch('/api/jobs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(taskData)
      })

      if (response.ok) {
        onTaskCreated('Task created successfully!')
      } else {
        throw new Error('Failed to create task')
      }
    } catch (error) {
      console.error('Error creating task:', error)
      alert('Error creating task: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content modal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h5 className="modal-title">
            <Plus size={20} className="me-2" />
            Create New Task
          </h5>
          <button type="button" className="btn-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        <div className="modal-body">
          <form onSubmit={handleSubmit}>
            <div className="row">
              <div className="col-md-6">
                <div className="mb-4">
                  <label htmlFor="taskType" className="form-label">
                    <CalendarClock size={16} className="me-1" />
                    Task Type
                  </label>
                  <select
                    className="form-select"
                    id="taskType"
                    value={taskType}
                    onChange={(e) => setTaskType(e.target.value)}
                    required
                  >
                    <option value="">Select task type...</option>
                    {taskTypes.map((type) => (
                      <option key={type.type} value={type.type}>
                        {type.name} - {type.description}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="col-md-6">
                <div className="mb-4">
                  <label htmlFor="taskName" className="form-label">
                    <Play size={16} className="me-1" />
                    Task Name/Description
                  </label>
                  <input
                    type="text"
                    className="form-control"
                    id="taskName"
                    value={taskName}
                    onChange={(e) => setTaskName(e.target.value)}
                    placeholder="Enter a descriptive name for this task"
                    required
                  />
                </div>
              </div>
            </div>

            <div className="mb-4">
              <label className="form-label">
                <Activity size={16} className="me-1" />
                Schedule
              </label>
              <div className="row align-items-end">
                <div className="col-md-4">
                  <select
                    className="form-select"
                    value={triggerType}
                    onChange={(e) => setTriggerType(e.target.value)}
                    required
                  >
                    <option value="interval">Interval</option>
                    <option value="cron">Cron</option>
                    <option value="date">Date</option>
                  </select>
                </div>
                <div className="col-md-8">
                  {triggerType === 'interval' && (
                    <div className="row g-3">
                      <div className="col-4">
                        <label htmlFor="hours" className="form-label d-flex align-items-center">
                          <Activity size={14} className="me-1" />
                          Hours
                        </label>
                        <input
                          type="number"
                          className="form-control"
                          id="hours"
                          value={hours}
                          onChange={(e) => setHours(e.target.value)}
                          min="0"
                        />
                      </div>
                      <div className="col-4">
                        <label htmlFor="minutes" className="form-label d-flex align-items-center">
                          <Activity size={14} className="me-1" />
                          Minutes
                        </label>
                        <input
                          type="number"
                          className="form-control"
                          id="minutes"
                          value={minutes}
                          onChange={(e) => setMinutes(e.target.value)}
                          min="0"
                          max="59"
                        />
                      </div>
                      <div className="col-4">
                        <label htmlFor="seconds" className="form-label d-flex align-items-center">
                          <Activity size={14} className="me-1" />
                          Seconds
                        </label>
                        <input
                          type="number"
                          className="form-control"
                          id="seconds"
                          value={seconds}
                          onChange={(e) => setSeconds(e.target.value)}
                          min="0"
                          max="59"
                        />
                      </div>
                    </div>
                  )}
                  {triggerType === 'cron' && (
                    <div>
                      <label htmlFor="cronExpression" className="form-label">
                        <Activity size={16} className="me-1" />
                        Cron Expression
                      </label>
                      <input
                        type="text"
                        className="form-control"
                        id="cronExpression"
                        value={cronExpression}
                        onChange={(e) => setCronExpression(e.target.value)}
                        placeholder="0 0 * * *"
                        title="Cron expression (minute hour day month day_of_week)"
                      />
                      <div className="form-text">
                        <small>Format: minute hour day month day_of_week (e.g., "0 0 * * *" for daily at midnight)</small>
                      </div>
                    </div>
                  )}
                  {triggerType === 'date' && (
                    <div>
                      <label htmlFor="runDate" className="form-label">
                        <Activity size={16} className="me-1" />
                        Run Date & Time
                      </label>
                      <input
                        type="datetime-local"
                        className="form-control"
                        id="runDate"
                        value={runDate}
                        onChange={(e) => setRunDate(e.target.value)}
                      />
                      <div className="form-text">
                        <small>Select the specific date and time to run this task</small>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="mb-4">
              <label className="form-label">
                <CalendarClock size={16} className="me-1" />
                Task Parameters
              </label>
              {taskType ? (
                <TaskParameters taskType={taskType} taskTypes={taskTypes} />
              ) : (
                <div className="alert alert-info">
                  <Activity size={16} className="me-2" />
                  <small>Parameters will appear here based on the selected task type</small>
                </div>
              )}
            </div>
          </form>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            <X size={16} className="me-1" />
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-success"
            onClick={handleSubmit}
            disabled={loading}
          >
            <Plus size={16} className="me-1" />
            {loading ? 'Creating...' : 'Create Task'}
          </button>
        </div>
      </div>
    </div>
  )
}

// View Task Modal Component
function ViewTaskModal({ task, onClose }) {
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleString()
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content modal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h5 className="modal-title">
            <Eye size={20} className="me-2" />
            Task Details
          </h5>
          <button type="button" className="btn-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        <div className="modal-body">
          <div className="row">
            <div className="col-md-6">
              <h6>Basic Information</h6>
              <table className="table table-sm">
                <tbody>
                  <tr>
                    <td><strong>ID:</strong></td>
                    <td><code>{task.id}</code></td>
                  </tr>
                  <tr>
                    <td><strong>Name:</strong></td>
                    <td>{task.name || 'Unnamed'}</td>
                  </tr>
                  <tr>
                    <td><strong>Function:</strong></td>
                    <td><code>{task.func || 'Unknown'}</code></td>
                  </tr>
                  <tr>
                    <td><strong>Status:</strong></td>
                    <td>
                      <span className={`badge ${task.next_run_time ? 'bg-success' : 'bg-warning'}`}>
                        {task.next_run_time ? 'Active' : 'Paused'}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="col-md-6">
              <h6>Schedule Information</h6>
              <table className="table table-sm">
                <tbody>
                  <tr>
                    <td><strong>Trigger:</strong></td>
                    <td>{task.trigger || 'Unknown'}</td>
                  </tr>
                  <tr>
                    <td><strong>Next Run:</strong></td>
                    <td>{task.next_run_time ? formatDate(task.next_run_time) : 'N/A'}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          {task.args && task.args.length > 0 && (
            <div className="mt-3">
              <h6>Arguments</h6>
              <pre className="code-block">{JSON.stringify(task.args, null, 2)}</pre>
            </div>
          )}
          {task.kwargs && Object.keys(task.kwargs).length > 0 && (
            <div className="mt-3">
              <h6>Keyword Arguments</h6>
              <pre className="code-block">{JSON.stringify(task.kwargs, null, 2)}</pre>
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            <X size={16} className="me-1" />
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

// Task Parameters Component
function TaskParameters({ taskType, taskTypes }) {
  const selectedTaskType = taskTypes.find(tt => tt.type === taskType)

  if (!selectedTaskType) {
    return (
      <div className="alert alert-info">
        <Activity size={16} className="me-2" />
        <small>Parameters will appear here based on the selected task type</small>
      </div>
    )
  }

  const renderParameter = (param, isRequired = false) => {
    // Specific parameter handling for known parameters
    switch(param) {
      case 'workspace_filter':
        return (
          <div>
            <label htmlFor={`param_${param}`} className="form-label">
              workspace_filter {isRequired && <span className="text-danger">*</span>}
            </label>
            <input
              type="text"
              className="form-control"
              id={`param_${param}`}
              placeholder="e.g., my-workspace-id"
              required={isRequired}
            />
            <div className="form-text">
              <small className="text-muted">Filter users by specific workspace ID (leave empty for all workspaces)</small>
            </div>
          </div>
        )

      case 'user_types':
        return (
          <div>
            <label htmlFor={`param_${param}`} className="form-label">
              user_types {isRequired && <span className="text-danger">*</span>}
            </label>
            <select className="form-select" id={`param_${param}`} multiple required={isRequired}>
              <option value="member" defaultSelected>Member</option>
              <option value="admin" defaultSelected>Admin</option>
              <option value="owner">Owner</option>
              <option value="bot">Bot</option>
            </select>
            <div className="form-text">
              <small className="text-muted">Select which types of users to import (hold Ctrl/Cmd to select multiple)</small>
            </div>
          </div>
        )

      case 'include_deactivated':
        return (
          <div>
            <label htmlFor={`param_${param}`} className="form-label">
              include_deactivated {isRequired && <span className="text-danger">*</span>}
            </label>
            <select className="form-select" id={`param_${param}`} required={isRequired}>
              <option value="false" defaultSelected>No - Active users only</option>
              <option value="true">Yes - Include deactivated users</option>
            </select>
            <div className="form-text">
              <small className="text-muted">Whether to include deactivated/deleted users in the import</small>
            </div>
          </div>
        )

      case 'folder_id':
        return (
          <div>
            <label htmlFor={`param_${param}`} className="form-label">
              folder_id {isRequired && <span className="text-danger">*</span>}
            </label>
            <input
              type="text"
              className="form-control"
              id={`param_${param}`}
              placeholder="Google Drive folder ID"
              required={isRequired}
            />
            <div className="form-text">
              <small className="text-muted">The Google Drive folder ID to ingest documents from</small>
            </div>
          </div>
        )

      case 'file_types':
        return (
          <div>
            <label htmlFor={`param_${param}`} className="form-label">
              file_types {isRequired && <span className="text-danger">*</span>}
            </label>
            <input
              type="text"
              className="form-control"
              id={`param_${param}`}
              placeholder="pdf,docx,txt"
              required={isRequired}
            />
            <div className="form-text">
              <small className="text-muted">Comma-separated list of file types to process (e.g., pdf,docx,txt)</small>
            </div>
          </div>
        )

      case 'force_update':
        return (
          <div>
            <label htmlFor={`param_${param}`} className="form-label">
              force_update {isRequired && <span className="text-danger">*</span>}
            </label>
            <select className="form-select" id={`param_${param}`} required={isRequired}>
              <option value="false" defaultSelected>No - Skip already processed files</option>
              <option value="true">Yes - Reprocess all files</option>
            </select>
            <div className="form-text">
              <small className="text-muted">Whether to reprocess files that have already been ingested</small>
            </div>
          </div>
        )

      case 'metadata':
        return (
          <div>
            <label htmlFor={`param_${param}`} className="form-label">
              metadata {isRequired && <span className="text-danger">*</span>}
            </label>
            <textarea
              className="form-control"
              id={`param_${param}`}
              rows="3"
              placeholder='{"project": "my-project", "department": "engineering"}'
              required={isRequired}
            />
            <div className="form-text">
              <small className="text-muted">Additional metadata as JSON object (optional)</small>
            </div>
          </div>
        )

      case 'metric_types':
        return (
          <div>
            <label htmlFor={`param_${param}`} className="form-label">
              metric_types {isRequired && <span className="text-danger">*</span>}
            </label>
            <select className="form-select" id={`param_${param}`} multiple required={isRequired}>
              <option value="system" defaultSelected>System Metrics</option>
              <option value="usage" defaultSelected>Usage Metrics</option>
              <option value="performance">Performance Metrics</option>
              <option value="errors">Error Metrics</option>
            </select>
            <div className="form-text">
              <small className="text-muted">Select which types of metrics to collect</small>
            </div>
          </div>
        )

      case 'time_range_hours':
        return (
          <div>
            <label htmlFor={`param_${param}`} className="form-label">
              time_range_hours {isRequired && <span className="text-danger">*</span>}
            </label>
            <input
              type="number"
              className="form-control"
              id={`param_${param}`}
              placeholder="24"
              min="1"
              max="168"
              defaultValue="24"
              required={isRequired}
            />
            <div className="form-text">
              <small className="text-muted">Number of hours to collect metrics for (1-168 hours)</small>
            </div>
          </div>
        )

      case 'aggregate_level':
        return (
          <div>
            <label htmlFor={`param_${param}`} className="form-label">
              aggregate_level {isRequired && <span className="text-danger">*</span>}
            </label>
            <select className="form-select" id={`param_${param}`} required={isRequired}>
              <option value="hourly" defaultSelected>Hourly</option>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
            </select>
            <div className="form-text">
              <small className="text-muted">Level of aggregation for collected metrics</small>
            </div>
          </div>
        )

      // Generic fallback for unknown parameters
      default:
        return (
          <div>
            <label htmlFor={`param_${param}`} className="form-label">
              {param} {isRequired && <span className="text-danger">*</span>}
            </label>
            <input
              type="text"
              className="form-control"
              id={`param_${param}`}
              placeholder={`Enter ${param}`}
              required={isRequired}
            />
            <div className="form-text">
              <small className="text-muted">Parameter: {param}</small>
            </div>
          </div>
        )
    }
  }

  return (
    <div>
      {/* Required Parameters */}
      {selectedTaskType.required_params && selectedTaskType.required_params.length > 0 && (
        <div className="mb-4">
          <h6>Required Parameters:</h6>
          {selectedTaskType.required_params.map((param) => (
            <div key={param} className="mb-3">
              {renderParameter(param, true)}
            </div>
          ))}
        </div>
      )}

      {/* Optional Parameters */}
      {selectedTaskType.optional_params && selectedTaskType.optional_params.length > 0 && (
        <div>
          <h6>Optional Parameters:</h6>
          {selectedTaskType.optional_params.map((param) => (
            <div key={param} className="mb-3">
              {renderParameter(param, false)}
            </div>
          ))}
        </div>
      )}

      {/* Show message if no parameters */}
      {(!selectedTaskType.required_params || selectedTaskType.required_params.length === 0) &&
       (!selectedTaskType.optional_params || selectedTaskType.optional_params.length === 0) && (
        <div className="alert alert-info">
          <Activity size={16} className="me-2" />
          <small>This task type has no configurable parameters</small>
        </div>
      )}
    </div>
  )
}

export default App
