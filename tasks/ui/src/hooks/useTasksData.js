import { useState, useCallback } from 'react'
import { logError } from '../utils/logger'
import { fetchWithTokenRefresh } from '../utils/tokenRefresh'

// Use relative URLs since the UI is served from the same nginx server
// This automatically uses the same protocol (HTTP/HTTPS) as the page
const API_BASE = '/api'
// Bot API base URL for RAG metrics (external service, use absolute URL)
const BOT_API_BASE = 'http://localhost:8080/api'

export function useTasksData() {
  const [schedulerData, setSchedulerData] = useState({})
  const [tasksData, setTasksData] = useState([])
  const [taskRunsData, setTaskRunsData] = useState([])
  const [taskRunsTotal, setTaskRunsTotal] = useState(0)
  const [ragMetrics, setRagMetrics] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Generic API call function with automatic token refresh
  const apiCall = useCallback(async (endpoint, options = {}) => {
    const response = await fetchWithTokenRefresh(`${API_BASE}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      ...options,
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
      logError('Error loading scheduler info:', error)
      setSchedulerData({ running: false, tasks_count: 0 })
    }
  }, [apiCall])

  // Load tasks/jobs
  const loadTasks = useCallback(async () => {
    try {
      const response = await apiCall('/jobs')
      setTasksData(response.jobs || [])
    } catch (error) {
      logError('Error loading tasks:', error)
      setTasksData([])
    }
  }, [apiCall])

  // Load task runs with pagination support
  const loadTaskRuns = useCallback(async (page = 1, perPage = 100) => {
    try {
      const response = await apiCall(`/task-runs?page=${page}&per_page=${perPage}`)
      setTaskRunsData(response.task_runs || [])
      setTaskRunsTotal(response.pagination?.total || 0)
      return response.pagination
    } catch (error) {
      logError('Error loading task runs:', error)
      setTaskRunsData([])
      setTaskRunsTotal(0)
      return null
    }
  }, [apiCall])

  // Load RAG metrics from bot service
  const loadRagMetrics = useCallback(async () => {
    try {
      const response = await fetchWithTokenRefresh(`${BOT_API_BASE}/metrics`, {
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      setRagMetrics(data.rag_performance || {})
    } catch (error) {
      logError('Error loading RAG metrics:', error)
      setRagMetrics({})
    }
  }, [])

  // Refresh all data
  const refreshData = useCallback(async (taskRunsPage = 1) => {
    setLoading(true)
    setError(null)

    try {
      await Promise.all([
        loadSchedulerInfo(),
        loadTasks(),
        loadTaskRuns(taskRunsPage),
        loadRagMetrics()
      ])
    } catch (error) {
      logError('Error refreshing data:', error)
      setError(error.message || 'Failed to refresh data')
    } finally {
      setLoading(false)
    }
  }, [loadSchedulerInfo, loadTasks, loadTaskRuns, loadRagMetrics])

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
    taskRunsTotal,
    ragMetrics,
    loading,
    error,
    refreshData,
    loadTaskRuns,
    pauseTask,
    resumeTask,
    deleteTask
  }
}
