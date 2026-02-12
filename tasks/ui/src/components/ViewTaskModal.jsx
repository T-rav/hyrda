import React, { useState, useEffect } from 'react'
import { Eye, X, Activity, CalendarClock } from 'lucide-react'
import TaskParameters from './TaskParameters'
import { logError } from '../utils/logger'

/**
 * ViewTaskModal Component
 *
 * Modal for viewing task details in read-only mode.
 * Displays task configuration using the same layout as the create form.
 *
 * @param {Object} task - The task object to display
 * @param {function} onClose - Callback to close the modal
 */
function ViewTaskModal({ task, onClose }) {
  const [taskTypes, setTaskTypes] = useState([])

  // Load task types to get parameter metadata
  useEffect(() => {
    const loadTaskTypes = async () => {
      try {
        const response = await fetch('/api/job-types', { credentials: 'include' })
        const data = await response.json()
        setTaskTypes(data.job_types || [])
      } catch (error) {
        logError('Error loading task types:', error)
      }
    }
    loadTaskTypes()
  }, [])

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleString()
  }

  // Extract task type from args (first element is the job type)
  const taskType = task.args && task.args.length > 0 ? task.args[0] : 'Unknown'

  // Extract parameters from args (second element is the params dict)
  const parameters = task.args && task.args.length > 1 ? task.args[1] : {}

  // Get human-readable trigger description
  const getTriggerDescription = () => {
    const trigger = task.trigger || 'Unknown'

    if (trigger.includes('interval')) {
      // Try to extract interval details from kwargs
      const kwargs = task.kwargs || {}
      const hours = kwargs.hours || 0
      const minutes = kwargs.minutes || 0
      const seconds = kwargs.seconds || 0

      const parts = []
      if (hours > 0) parts.push(`${hours} hour${hours !== 1 ? 's' : ''}`)
      if (minutes > 0) parts.push(`${minutes} minute${minutes !== 1 ? 's' : ''}`)
      if (seconds > 0) parts.push(`${seconds} second${seconds !== 1 ? 's' : ''}`)

      return parts.length > 0 ? `Every ${parts.join(', ')}` : 'Interval'
    }

    if (trigger.includes('cron')) {
      // Try to extract cron details
      const kwargs = task.kwargs || {}
      const minute = kwargs.minute !== undefined ? kwargs.minute : '*'
      const hour = kwargs.hour !== undefined ? kwargs.hour : '*'
      const day = kwargs.day !== undefined ? kwargs.day : '*'
      const month = kwargs.month !== undefined ? kwargs.month : '*'
      const dayOfWeek = kwargs.day_of_week !== undefined ? kwargs.day_of_week : '*'

      const cronExpr = `${minute} ${hour} ${day} ${month} ${dayOfWeek}`

      // Common patterns
      if (cronExpr === '0 * * * *') return 'Hourly'
      if (cronExpr === '0 0 * * *') return 'Daily at midnight'
      if (cronExpr === '0 9 * * *') return 'Daily at 9:00 AM'
      if (cronExpr === '0 9 * * 1') return 'Weekly (Monday 9:00 AM)'
      if (cronExpr === '0 0 1 * *') return 'Monthly (1st of month)'

      return `Cron: ${cronExpr}`
    }

    if (trigger.includes('date')) {
      return 'One-time scheduled run'
    }

    return trigger
  }

  // Get status badge
  const getStatusBadge = () => {
    const isActive = !!task.next_run_time

    return isActive ? (
      <span className="badge bg-success">Active</span>
    ) : (
      <span className="badge bg-warning">Paused</span>
    )
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content modal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h5 className="modal-title">
            <Eye size={20} className="me-2" />
            {task.name || taskType}
          </h5>
          <button type="button" className="btn-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        <div className="modal-body" style={{ fontSize: '14px' }}>
          {/* Main Info Grid */}
          <div className="row g-3 mb-4">
            <div className="col-md-6">
              <div className="p-3 border rounded">
                <div className="text-muted small mb-1">TASK TYPE</div>
                <div className="fw-bold"><code>{taskType}</code></div>
              </div>
            </div>
            <div className="col-md-6">
              <div className="p-3 border rounded">
                <div className="text-muted small mb-1">SCHEDULE</div>
                <div className="fw-bold">{getTriggerDescription()}</div>
              </div>
            </div>
          </div>

          <div className="row g-3 mb-4">
            <div className="col-md-6">
              <div className="p-3 border rounded">
                <div className="text-muted small mb-1">STATUS</div>
                <div>{getStatusBadge()}</div>
              </div>
            </div>
            <div className="col-md-6">
              <div className="p-3 border rounded">
                <div className="text-muted small mb-1">NEXT RUN</div>
                <div className="fw-bold">
                  {task.next_run_time ? formatDate(task.next_run_time) : 'Paused'}
                </div>
              </div>
            </div>
          </div>

          {/* Task Parameters Section */}
          <div className="mb-4">
            <div className="d-flex align-items-center mb-3">
              <CalendarClock size={16} className="me-2" />
              <h6 className="mb-0">Task Parameters</h6>
            </div>
            {taskTypes.length > 0 ? (
              <TaskParameters
                taskType={taskType}
                taskTypes={taskTypes}
                values={parameters}
                readOnly={true}
              />
            ) : (
              <div className="alert alert-info">
                <Activity size={16} className="me-2" />
                <small>Loading parameter details...</small>
              </div>
            )}
          </div>

          {/* Task ID */}
          <div className="text-muted small border-top pt-3">
            <div className="row">
              <div className="col-md-6">
                <strong>Task ID:</strong> <code className="text-muted">{task.id}</code>
              </div>
              {task.pending !== undefined && (
                <div className="col-md-6">
                  <strong>Pending:</strong> {task.pending ? 'Yes' : 'No'}
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-outline-secondary" onClick={onClose}>
            <X size={16} className="me-1" />
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export default ViewTaskModal
