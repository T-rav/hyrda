import React, { useState, useEffect } from 'react'
import { Plus, X, Activity, CalendarClock, Play } from 'lucide-react'
import TaskParameters from './TaskParameters'
import { logError } from '../utils/logger'

/**
 * CreateTaskModal Component
 *
 * Modal for creating new scheduled tasks.
 * Includes task type selection, naming, scheduling, and parameter configuration.
 *
 * @param {function} onClose - Callback to close the modal
 * @param {function} onTaskCreated - Callback when task is created successfully (message) => void
 */
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
  const [parameters, setParameters] = useState({})

  // Load task types on component mount
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

  // Reset parameters when task type changes
  useEffect(() => {
    setParameters({})
  }, [taskType])

  const handleParameterChange = (param, value) => {
    setParameters(prev => ({
      ...prev,
      [param]: value,
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!taskType || !taskName) {
      alert('Please fill in all required fields')
      return
    }

    // Validate credential_id for gdrive_ingest
    if (taskType === 'gdrive_ingest' && !parameters.credential_id) {
      alert('Please select a Google Drive credential from the dropdown.')
      return
    }

    // Validate that at least one of folder_id or file_id is provided for gdrive_ingest
    if (taskType === 'gdrive_ingest') {
      const hasFolderId = parameters.folder_id && parameters.folder_id.trim() !== ''
      const hasFileId = parameters.file_id && parameters.file_id.trim() !== ''

      if (!hasFolderId && !hasFileId) {
        alert('Please provide either a Folder ID or File ID.')
        return
      }
    }

    setLoading(true)
    try {
      const schedule = {
        trigger: triggerType,
      }

      if (triggerType === 'interval') {
        schedule.hours = parseInt(hours) || 0
        schedule.minutes = parseInt(minutes) || 0
        schedule.seconds = parseInt(seconds) || 0
      } else if (triggerType === 'cron') {
        // Parse cron expression into components
        const parts = cronExpression.trim().split(/\s+/)
        if (parts.length === 5) {
          schedule.minute = parts[0]
          schedule.hour = parts[1]
          schedule.day = parts[2]
          schedule.month = parts[3]
          schedule.day_of_week = parts[4]
        }
      } else if (triggerType === 'date') {
        if (runDate) {
          schedule.run_date = new Date(runDate).toISOString()
        }
      }

      const taskData = {
        job_type: taskType,
        task_name: taskName,
        schedule: schedule,
        parameters: parameters,
      }

      const response = await fetch('/api/jobs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(taskData),
      })

      if (response.ok) {
        onTaskCreated('Task created successfully!')
      } else {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to create task')
      }
    } catch (error) {
      logError('Error creating task:', error)
      alert('Error creating task: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  // Quick schedule presets
  const schedulePresets = [
    { label: '15 min', hours: '0', minutes: '15', seconds: '0' },
    { label: '30 min', hours: '0', minutes: '30', seconds: '0' },
    { label: '1 hour', hours: '1', minutes: '0', seconds: '0' },
    { label: '6 hours', hours: '6', minutes: '0', seconds: '0' },
    { label: '24 hours', hours: '24', minutes: '0', seconds: '0' },
  ]

  const applyPreset = (preset) => {
    setHours(preset.hours)
    setMinutes(preset.minutes)
    setSeconds(preset.seconds)
  }

  // Cron presets
  const cronPresets = [
    { label: 'Hourly', value: '0 * * * *' },
    { label: 'Daily at midnight', value: '0 0 * * *' },
    { label: 'Daily at 9am', value: '0 9 * * *' },
    { label: 'Weekly (Mon 9am)', value: '0 9 * * 1' },
    { label: 'Monthly (1st)', value: '0 0 1 * *' },
  ]

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
                    Task Name
                  </label>
                  <input
                    type="text"
                    className="form-control"
                    id="taskName"
                    value={taskName}
                    onChange={(e) => setTaskName(e.target.value)}
                    placeholder="Enter a name for this task"
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
                    <div>
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
                      <div className="mt-2">
                        <small className="text-muted">Quick presets: </small>
                        {schedulePresets.map((preset) => (
                          <button
                            key={preset.label}
                            type="button"
                            className="btn btn-sm btn-outline-secondary me-1 mt-1"
                            onClick={() => applyPreset(preset)}
                          >
                            {preset.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {triggerType === 'cron' && (
                    <div>
                      <div className="mb-2">
                        <small className="text-muted">Quick presets: </small>
                        {cronPresets.map((preset) => (
                          <button
                            key={preset.label}
                            type="button"
                            className="btn btn-sm btn-outline-secondary me-1 mt-1"
                            onClick={() => setCronExpression(preset.value)}
                          >
                            {preset.label}
                          </button>
                        ))}
                      </div>
                      <input
                        type="text"
                        className="form-control"
                        id="cronExpression"
                        value={cronExpression}
                        onChange={(e) => setCronExpression(e.target.value)}
                        placeholder="0 0 * * *"
                        title="Cron expression (minute hour day month day_of_week)"
                      />
                      <div className="form-text mt-1">
                        <small>Format: minute hour day month day_of_week (e.g., &quot;0 0 * * *&quot; for daily at midnight)</small>
                      </div>
                    </div>
                  )}
                  {triggerType === 'date' && (
                    <div>
                      <input
                        type="datetime-local"
                        className="form-control"
                        id="runDate"
                        value={runDate}
                        onChange={(e) => setRunDate(e.target.value)}
                      />
                      <div className="form-text mt-1">
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
                <TaskParameters
                  taskType={taskType}
                  taskTypes={taskTypes}
                  values={parameters}
                  onChange={handleParameterChange}
                  readOnly={false}
                />
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
          <button type="button" className="btn btn-outline-secondary" onClick={onClose}>
            <X size={16} className="me-1" />
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-outline-success"
            onClick={handleSubmit}
            disabled={loading || !taskType}
          >
            <Plus size={16} className="me-1" />
            {loading ? 'Creating...' : 'Create Task'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default CreateTaskModal
