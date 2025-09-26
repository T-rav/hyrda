import { useState, useCallback } from 'react'

// API base URL - tasks service runs on port 5001
const API_BASE = 'http://localhost:5001/api'

export function useTasksData() {
  const [schedulerData, setSchedulerData] = useState({})
  const [tasksData, setTasksData] = useState([])
  const [taskRunsData, setTaskRunsData] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Generic API call function
  const apiCall = useCallback(async (endpoint) => {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return response.json()
  }, [])

  // Load scheduler info
  const loadSchedulerInfo = useCallback(async () => {
    try {
      const data = await apiCall('/scheduler/info')
      setSchedulerData(data)
    } catch (error) {
      console.error('Error loading scheduler info:', error)
      setSchedulerData({ running: false, tasks_count: 0 })
    }
  }, [apiCall])

  // Load tasks/jobs
  const loadTasks = useCallback(async () => {
    try {
      const response = await apiCall('/jobs')
      setTasksData(response.jobs || [])
    } catch (error) {
      console.error('Error loading tasks:', error)
      setTasksData([])
    }
  }, [apiCall])

  // Load task runs
  const loadTaskRuns = useCallback(async () => {
    try {
      const response = await apiCall('/task-runs')
      setTaskRunsData(response.task_runs || [])
    } catch (error) {
      console.error('Error loading task runs:', error)
      setTaskRunsData([])
    }
  }, [apiCall])

  // Refresh all data
  const refreshData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      await Promise.all([
        loadSchedulerInfo(),
        loadTasks(),
        loadTaskRuns()
      ])
    } catch (error) {
      console.error('Error refreshing data:', error)
      setError(error.message || 'Failed to refresh data')
    } finally {
      setLoading(false)
    }
  }, [loadSchedulerInfo, loadTasks, loadTaskRuns])

  // Task action functions
  const pauseTask = useCallback(async (taskId) => {
    try {
      await apiCall(`/jobs/${taskId}/pause`, { method: 'POST' })
      await refreshData() // Refresh data after action
      return { success: true, message: `Task ${taskId} paused successfully` }
    } catch (error) {
      const message = `Error pausing task: ${error.message}`
      setError(message)
      return { success: false, message }
    }
  }, [apiCall, refreshData])

  const resumeTask = useCallback(async (taskId) => {
    try {
      await apiCall(`/jobs/${taskId}/resume`, { method: 'POST' })
      await refreshData() // Refresh data after action
      return { success: true, message: `Task ${taskId} resumed successfully` }
    } catch (error) {
      const message = `Error resuming task: ${error.message}`
      setError(message)
      return { success: false, message }
    }
  }, [apiCall, refreshData])

  const deleteTask = useCallback(async (taskId) => {
    try {
      await apiCall(`/jobs/${taskId}`, { method: 'DELETE' })
      await refreshData() // Refresh data after action
      return { success: true, message: `Task ${taskId} deleted successfully` }
    } catch (error) {
      const message = `Error deleting task: ${error.message}`
      setError(message)
      return { success: false, message }
    }
  }, [apiCall, refreshData])

  return {
    schedulerData,
    tasksData,
    taskRunsData,
    loading,
    error,
    refreshData,
    pauseTask,
    resumeTask,
    deleteTask
  }
}
