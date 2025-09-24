import React, { useState, useEffect } from 'react'
import { ListChecks, Play, Pause, Trash2, RefreshCw } from 'lucide-react'
import { useTasksData } from '../hooks/useTasksData'

function TasksList({ onError, setLoading }) {
  const {
    tasksData,
    loading,
    error,
    refreshData,
    pauseTask,
    resumeTask,
    deleteTask
  } = useTasksData()

  const [actionLoading, setActionLoading] = useState({})

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

  // Initial load
  useEffect(() => {
    refreshData()
  }, [refreshData])

  const handleTaskAction = async (action, taskId) => {
    setActionLoading({ ...actionLoading, [taskId]: action })

    let result
    switch (action) {
      case 'pause':
        result = await pauseTask(taskId)
        break
      case 'resume':
        result = await resumeTask(taskId)
        break
      case 'delete':
        if (window.confirm(`Are you sure you want to delete task ${taskId}?`)) {
          result = await deleteTask(taskId)
        } else {
          setActionLoading({ ...actionLoading, [taskId]: null })
          return
        }
        break
      default:
        break
    }

    setActionLoading({ ...actionLoading, [taskId]: null })

    // Show result message (in real app, you'd use a toast system)
    if (result) {
      console.log(result.message)
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
      {/* Tasks Header */}
      <div className="glass-card mb-4">
        <div className="card-header">
          <div className="header-title">
            <ListChecks size={24} />
            <h2>Tasks</h2>
          </div>
          <div className="header-actions">
            <button
              className="btn btn-outline-secondary"
              onClick={refreshData}
              disabled={loading}
            >
              <RefreshCw size={16} className={loading ? 'spinning' : ''} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Tasks Table */}
      <div className="glass-card">
        <div className="table-container">
          {tasksData.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📋</div>
              <p>No tasks configured</p>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Task Name</th>
                  <th>Status</th>
                  <th>Next Run</th>
                  <th>Schedule</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {tasksData.map((task) => (
                  <tr key={task.id}>
                    <td>
                      <div className="task-name">
                        <strong>{task.name || task.id}</strong>
                        {task.description && (
                          <small className="text-muted d-block">{task.description}</small>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${
                        task.next_run_time ? 'bg-success' : 'bg-warning'
                      }`}>
                        {task.next_run_time ? 'Active' : 'Paused'}
                      </span>
                    </td>
                    <td>
                      <span className="next-run">
                        {formatNextRun(task.next_run_time)}
                      </span>
                    </td>
                    <td>
                      <code className="schedule">
                        {task.trigger || 'Unknown'}
                      </code>
                    </td>
                    <td>
                      <div className="task-actions">
                        {task.next_run_time ? (
                          <button
                            className="btn btn-sm btn-outline-warning me-2"
                            onClick={() => handleTaskAction('pause', task.id)}
                            disabled={actionLoading[task.id] === 'pause'}
                            title="Pause Task"
                          >
                            <Pause size={14} />
                            {actionLoading[task.id] === 'pause' ? 'Pausing...' : 'Pause'}
                          </button>
                        ) : (
                          <button
                            className="btn btn-sm btn-outline-success me-2"
                            onClick={() => handleTaskAction('resume', task.id)}
                            disabled={actionLoading[task.id] === 'resume'}
                            title="Resume Task"
                          >
                            <Play size={14} />
                            {actionLoading[task.id] === 'resume' ? 'Resuming...' : 'Resume'}
                          </button>
                        )}
                        <button
                          className="btn btn-sm btn-outline-danger"
                          onClick={() => handleTaskAction('delete', task.id)}
                          disabled={actionLoading[task.id] === 'delete'}
                          title="Delete Task"
                        >
                          <Trash2 size={14} />
                          {actionLoading[task.id] === 'delete' ? 'Deleting...' : 'Delete'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}

export default TasksList
