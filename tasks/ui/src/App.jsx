import React, { useState } from 'react'
import { CalendarClock, LayoutDashboard, ListChecks, Activity, ArrowRight, ArrowUp, ChevronLeft, ChevronRight, ChevronDown, Play, Pause, Trash2, RefreshCw, PlayCircle, Eye, Plus, X, Key, LogOut, User, Folder } from 'lucide-react'
import CredentialsManager from './components/CredentialsManager'
import CreateTaskModal from './components/CreateTaskModal'
import ViewTaskModal from './components/ViewTaskModal'
import './App.css'
import { logError } from './utils/logger'
import { setupTokenRefresh, fetchWithTokenRefresh } from './utils/tokenRefresh'

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
  const [currentUserEmail, setCurrentUserEmail] = useState(null)

  // Lifted state - SHARED between Dashboard and Tasks
  const [jobs, setJobs] = useState([])
  const [taskRuns, setTaskRuns] = useState([])
  const [scheduler, setScheduler] = useState({})
  const [loading, setLoading] = useState(false)

  // Use the custom hook to set document title
  useDocumentTitle('InsightMesh - Tasks Dashboard')

  // Check authentication on mount
  React.useEffect(() => {
    const verifyAuth = async () => {
      try {
        const response = await fetch('/auth/me', {
          credentials: 'include'
        })
        if (!response.ok) {
          // Not authenticated - redirect to control plane login with redirect back to tasks
          window.location.href = 'https://localhost:6001/auth/start?redirect=https://localhost:5001'
          return
        }
        const data = await response.json()
        if (data.email) {
          setCurrentUserEmail(data.email)
        }
      } catch (error) {
        logError('Auth check failed:', error)
        window.location.href = 'https://localhost:6001/auth/start?redirect=https://localhost:5001'
        return
      }
    }

    verifyAuth()
    // Setup automatic token refresh (checks token every 5 minutes)
    setupTokenRefresh()
  }, [])

  const handleTabChange = (tab) => {
    setActiveTab(tab)
  }

  const showNotification = (message, type = 'success') => {
    setNotification({ message, type })
    setTimeout(() => setNotification(null), 3000)
  }

  const handleLogout = () => {
    // POST to logout endpoint
    const form = document.createElement('form')
    form.method = 'POST'
    form.action = 'https://localhost:6001/auth/logout'
    document.body.appendChild(form)
    form.submit()
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
            <div className="logout-dropdown">
              <button
                className="nav-link logout-btn"
                onClick={handleLogout}
                title="Logout"
              >
                <LogOut size={20} />
                Logout
              </button>
              {currentUserEmail && (
                <div className="dropdown-menu">
                  <div className="dropdown-item user-email">
                    <User size={16} />
                    {currentUserEmail}
                  </div>
                </div>
              )}
            </div>
          </nav>
        </div>
      </header>

      <main className="main-content">
        {activeTab === 'dashboard' && (
          <DashboardContent
            showNotification={showNotification}
            jobs={jobs}
            setJobs={setJobs}
            taskRuns={taskRuns}
            setTaskRuns={setTaskRuns}
            scheduler={scheduler}
            setScheduler={setScheduler}
            loading={loading}
            setLoading={setLoading}
          />
        )}
        {activeTab === 'tasks' && (
          <TasksContent
            showNotification={showNotification}
            jobs={jobs}
            setJobs={setJobs}
            loading={loading}
            setLoading={setLoading}
          />
        )}
        {activeTab === 'credentials' && <CredentialsManager />}
      </main>

      <footer className="footer">
        <p>InsightMesh Tasks</p>
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
function DashboardContent({ jobs, setJobs, taskRuns, setTaskRuns, setScheduler, loading, setLoading }) {
  const [showAllRuns, setShowAllRuns] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const recordsPerPage = 20
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(null)
  const [taskRunsPagination, setTaskRunsPagination] = useState({ total: 0, page: 1, has_next: false })
  const [loadingMore, setLoadingMore] = useState(false)

  const loadData = async () => {
    setLoading(true)
    try {
      const [jobsRes, runsRes, schedulerRes] = await Promise.all([
        fetchWithTokenRefresh('/api/jobs').then(async r => {
          if (!r.ok) throw new Error(`Failed to load jobs: ${r.status}`)
          return r.json()
        }),
        fetchWithTokenRefresh('/api/task-runs').then(async r => {
          if (!r.ok) throw new Error(`Failed to load task runs: ${r.status}`)
          return r.json()
        }),
        fetchWithTokenRefresh('/api/scheduler/info').then(async r => {
          if (!r.ok) throw new Error(`Failed to load scheduler info: ${r.status}`)
          return r.json()
        })
      ])

      setJobs(jobsRes.jobs || [])
      setTaskRuns(runsRes.task_runs || [])
      setTaskRunsPagination(runsRes.pagination || { total: 0, page: 1, has_next: false })
      setScheduler(schedulerRes)
    } catch (error) {
      logError('Error loading data:', error)
      setJobs([])
      setTaskRuns([])
      setScheduler({ running: false })
    } finally {
      setLoading(false)
    }
  }

  // Load more task runs (next page)
  const loadMoreRuns = async () => {
    if (!taskRunsPagination.has_next || loadingMore) return

    setLoadingMore(true)
    try {
      const nextPage = taskRunsPagination.page + 1
      const response = await fetchWithTokenRefresh(`/api/task-runs?page=${nextPage}`)
      if (!response.ok) throw new Error(`Failed to load more runs: ${response.status}`)
      const data = await response.json()

      // Append new runs to existing
      setTaskRuns(prev => [...prev, ...(data.task_runs || [])])
      setTaskRunsPagination(data.pagination || { total: 0, page: nextPage, has_next: false })
    } catch (error) {
      logError('Error loading more runs:', error)
    } finally {
      setLoadingMore(false)
    }
  }

  // Load data on component mount (only if not already loaded)
  React.useEffect(() => {
    if (jobs.length === 0 && taskRuns.length === 0) {
      loadData()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh])

  const toggleAutoRefresh = () => {
    setAutoRefresh(!autoRefresh)
  }

  // Calculate statistics
  const totalTasks = jobs.length
  const activeTasks = jobs.filter(job => job.next_run_time).length
  const pausedTasks = jobs.filter(job => !job.next_run_time).length

  // Calculate next run
  const nextRuns = jobs
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

  // Calculate success rate (use actual total from pagination, success rate from loaded data)
  const totalRuns = taskRunsPagination.total || taskRuns.length
  const successfulRuns = taskRuns.filter(run => run.status === 'success').length
  const loadedRuns = taskRuns.length
  const successRate = loadedRuns > 0 ? Math.round((successfulRuns / loadedRuns) * 100) : 0

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
              {successRate}% ({successfulRuns}/{loadedRuns} loaded)
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
          taskRuns={taskRuns}
          showAllRuns={showAllRuns}
          currentPage={currentPage}
          recordsPerPage={recordsPerPage}
          onPageChange={setCurrentPage}
          pagination={taskRunsPagination}
          onLoadMore={loadMoreRuns}
          loadingMore={loadingMore}
        />
      </div>
    </div>
  )
}

// Full Tasks Component with Management
function TasksContent({ showNotification, jobs, setJobs, loading, setLoading }) {
  const [actionLoading, setActionLoading] = useState({})
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showViewModal, setShowViewModal] = useState(false)
  const [selectedTask, setSelectedTask] = useState(null)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(null)
  const [expandedGroups, setExpandedGroups] = useState({})

  const loadTasks = async () => {
    setLoading(true)
    try {
      const response = await fetchWithTokenRefresh('/api/jobs')
      if (!response.ok) {
        throw new Error(`Failed to load tasks: ${response.status}`)
      }
      const data = await response.json()
      setJobs(data.jobs || [])
    } catch (error) {
      logError('Error loading tasks:', error)
      setJobs([])
    } finally {
      setLoading(false)
    }
  }

  // Load data on component mount (only if not already loaded)
  React.useEffect(() => {
    if (jobs.length === 0) {
      loadTasks()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
          response = await fetchWithTokenRefresh(`/api/jobs/${taskId}/pause`, { method: 'POST' })
          if (response && response.ok) {
            const task = jobs.find(t => t.id === taskId)
            const taskName = getTaskDisplayName(task)
            showNotification(`${taskName} paused successfully`, 'success')
            await loadTasks()
          } else {
            throw new Error('Failed to pause task')
          }
          break
        case 'resume':
          response = await fetchWithTokenRefresh(`/api/jobs/${taskId}/resume`, { method: 'POST' })
          if (response && response.ok) {
            const task = jobs.find(t => t.id === taskId)
            const taskName = getTaskDisplayName(task)
            showNotification(`${taskName} resumed successfully`, 'success')
            await loadTasks()
          } else {
            throw new Error('Failed to resume task')
          }
          break
        case 'run-once':
          response = await fetchWithTokenRefresh(`/api/jobs/${taskId}/run-once`, { method: 'POST' })
          if (response && response.ok) {
            const task = jobs.find(t => t.id === taskId)
            const taskName = getTaskDisplayName(task)
            showNotification(`${taskName} triggered successfully`, 'success')
            await loadTasks()
          } else {
            throw new Error('Failed to trigger task')
          }
          break
        case 'delete':
          const task = jobs.find(t => t.id === taskId)
          const taskName = getTaskDisplayName(task)
          if (window.confirm(`Are you sure you want to delete ${taskName}?`)) {
            response = await fetchWithTokenRefresh(`/api/jobs/${taskId}`, { method: 'DELETE' })
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
            const taskResponse = await fetchWithTokenRefresh(`/api/jobs/${taskId}`)
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

  // Group jobs by group_name
  const groupedJobs = React.useMemo(() => {
    const groups = {}
    jobs.forEach(job => {
      const groupKey = job.group_name || '__ungrouped__'
      if (!groups[groupKey]) {
        groups[groupKey] = []
      }
      groups[groupKey].push(job)
    })
    // Sort groups alphabetically, with ungrouped last (at bottom)
    const sortedKeys = Object.keys(groups).sort((a, b) => {
      if (a === '__ungrouped__') return 1
      if (b === '__ungrouped__') return -1
      return a.localeCompare(b)
    })
    return sortedKeys.map(key => ({
      name: key === '__ungrouped__' ? null : key,
      tasks: groups[key]
    }))
  }, [jobs])

  const toggleGroup = (groupName) => {
    setExpandedGroups(prev => ({
      ...prev,
      [groupName || '__ungrouped__']: !prev[groupName || '__ungrouped__']
    }))
  }

  const isGroupExpanded = (groupName) => {
    return expandedGroups[groupName || '__ungrouped__'] || false
  }

  // Handle group actions (pause/resume/run-once/delete all tasks in group)
  const handleGroupAction = async (action, groupTasks) => {
    const groupName = groupTasks[0]?.group_name || 'Ungrouped'

    if (action === 'delete') {
      if (!window.confirm(`Are you sure you want to delete all ${groupTasks.length} tasks in "${groupName}"?`)) {
        return
      }
    }

    setActionLoading(prev => ({ ...prev, [`group_${groupName}`]: action }))

    try {
      for (const task of groupTasks) {
        let response
        switch (action) {
          case 'pause':
            if (task.next_run_time) { // Only pause active tasks
              response = await fetchWithTokenRefresh(`/api/jobs/${task.id}/pause`, { method: 'POST' })
              if (!response.ok) throw new Error(`Failed to pause ${task.name}`)
            }
            break
          case 'resume':
            if (!task.next_run_time) { // Only resume paused tasks
              response = await fetchWithTokenRefresh(`/api/jobs/${task.id}/resume`, { method: 'POST' })
              if (!response.ok) throw new Error(`Failed to resume ${task.name}`)
            }
            break
          case 'run-once':
            response = await fetchWithTokenRefresh(`/api/jobs/${task.id}/run-once`, { method: 'POST' })
            if (!response.ok) throw new Error(`Failed to run ${task.name}`)
            break
          case 'delete':
            response = await fetchWithTokenRefresh(`/api/jobs/${task.id}`, { method: 'DELETE' })
            if (!response.ok) throw new Error(`Failed to delete ${task.name}`)
            break
          default:
            break
        }
      }

      const actionVerb = action === 'pause' ? 'paused' :
                         action === 'resume' ? 'resumed' :
                         action === 'run-once' ? 'triggered' : 'deleted'
      showNotification(`All tasks in "${groupName}" ${actionVerb} successfully`, 'success')
      await loadTasks()
    } catch (error) {
      logError(`Error ${action} group:`, error)
      showNotification(`Error: ${error.message}`, 'error')
    } finally {
      setActionLoading(prev => ({ ...prev, [`group_${groupName}`]: null }))
    }
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
            <span className="badge bg-primary ms-2">{jobs.length}</span>
          </div>
        </div>

        <div className="table-container">
          {jobs.length === 0 ? (
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
                {groupedJobs.map((group) => (
                  <React.Fragment key={group.name || '__ungrouped__'}>
                    {/* Ungrouped tasks render directly without a group header */}
                    {!group.name ? (
                      group.tasks.map((task) => (
                        <TaskRow
                          key={task.id}
                          task={task}
                          onAction={handleTaskAction}
                          actionLoading={actionLoading}
                          formatNextRun={formatNextRun}
                          isGrouped={false}
                        />
                      ))
                    ) : (
                      <>
                        {/* Group Header Row */}
                        <GroupRow
                          group={group}
                          isExpanded={isGroupExpanded(group.name)}
                          onToggle={() => toggleGroup(group.name)}
                          onGroupAction={handleGroupAction}
                          actionLoading={actionLoading}
                        />
                        {/* Task Rows (when expanded) */}
                        {isGroupExpanded(group.name) && group.tasks.map((task) => (
                          <TaskRow
                            key={task.id}
                            task={task}
                            onAction={handleTaskAction}
                            actionLoading={actionLoading}
                            formatNextRun={formatNextRun}
                            isGrouped={true}
                          />
                        ))}
                      </>
                    )}
                  </React.Fragment>
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

// Group Row Component (collapsible header)
function GroupRow({ group, isExpanded, onToggle, onGroupAction, actionLoading }) {
  const groupName = group.name || 'Ungrouped'
  const taskCount = group.tasks.length
  const activeCount = group.tasks.filter(t => t.next_run_time).length
  const pausedCount = taskCount - activeCount
  const currentAction = actionLoading[`group_${groupName}`]

  // Determine if we should show pause or resume based on majority
  const showPause = activeCount > pausedCount

  return (
    <tr className="group-row" style={{ backgroundColor: group.name ? 'rgba(99, 102, 241, 0.1)' : 'rgba(156, 163, 175, 0.1)' }}>
      <td>
        <div style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }} onClick={onToggle}>
          {isExpanded ? (
            <ChevronDown size={18} className="me-2" />
          ) : (
            <ChevronRight size={18} className="me-2" />
          )}
          {group.name ? (
            <Folder size={16} className="me-2" style={{ color: '#6366f1' }} />
          ) : null}
          <strong style={{ fontSize: '1rem' }}>{groupName}</strong>
          <span className="badge bg-primary ms-2">{taskCount} task{taskCount !== 1 ? 's' : ''}</span>
          {!isExpanded && (
            <>
              {activeCount > 0 && <span className="badge bg-success ms-2">{activeCount} active</span>}
              {pausedCount > 0 && <span className="badge bg-warning ms-2">{pausedCount} paused</span>}
            </>
          )}
        </div>
      </td>
      <td></td>
      <td></td>
      <td>
        <div className="btn-group btn-group-sm" role="group">
          <button
            className="btn btn-outline-primary btn-sm"
            disabled={true}
            title="View (select individual task)"
          >
            <Eye size={12} />
          </button>
          <button
            className={`btn ${showPause ? 'btn-outline-warning' : 'btn-outline-success'} btn-sm`}
            onClick={(e) => { e.stopPropagation(); onGroupAction(showPause ? 'pause' : 'resume', group.tasks) }}
            disabled={currentAction === 'pause' || currentAction === 'resume'}
            title={showPause ? 'Pause All' : 'Resume All'}
          >
            {showPause ? <Pause size={12} /> : <Play size={12} />}
          </button>
          <button
            className="btn btn-outline-info btn-sm"
            onClick={(e) => { e.stopPropagation(); onGroupAction('run-once', group.tasks) }}
            disabled={currentAction === 'run-once'}
            title="Run All Once"
          >
            <PlayCircle size={12} />
          </button>
          <button
            className="btn btn-outline-danger btn-sm"
            onClick={(e) => { e.stopPropagation(); onGroupAction('delete', group.tasks) }}
            disabled={currentAction === 'delete'}
            title="Delete All"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </td>
    </tr>
  )
}

// Task Row Component
function TaskRow({ task, onAction, actionLoading, formatNextRun, isGrouped = false }) {
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
    <tr style={isGrouped ? { backgroundColor: 'rgba(99, 102, 241, 0.03)' } : {}}>
      <td style={isGrouped ? { paddingLeft: '2.5rem' } : {}}>
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
function RecentRunsTable({ taskRuns, showAllRuns, currentPage, recordsPerPage, onPageChange, pagination, onLoadMore, loadingMore }) {
  const totalFromServer = pagination?.total || taskRuns.length
  const hasMore = pagination?.has_next || false

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

  // Pagination info (use loaded count for local pagination)
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
      {showAllRuns && (
        <div className="pagination-controls">
          <div className="pagination-info">
            <span className="text-muted">
              Showing {startRecord}-{endRecord} of {taskRuns.length} loaded ({totalFromServer} total)
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

            {/* Load More button when at last page of loaded data but more exists on server */}
            {currentPage === totalPages && hasMore && (
              <button
                className="btn btn-sm btn-outline-primary ms-3"
                onClick={onLoadMore}
                disabled={loadingMore}
              >
                {loadingMore ? 'Loading...' : 'Load 50 more'}
              </button>
            )}
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
            {run.group_name && (
              <span className="badge bg-secondary me-2">{run.group_name}</span>
            )}
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
