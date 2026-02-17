import { useState } from 'react'

export function useGoalBots(toast) {
  const [goalBots, setGoalBots] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedBot, setSelectedBot] = useState(null)
  const [selectedBotDetails, setSelectedBotDetails] = useState(null)
  const [showCreateModal, setShowCreateModal] = useState(false)

  const fetchGoalBots = async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true)
      const response = await fetch('/api/goal-bots', { credentials: 'include' })
      if (!response.ok) throw new Error('Failed to fetch goal bots')
      const data = await response.json()
      setGoalBots(data.goal_bots || [])
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      if (showLoading) setLoading(false)
    }
  }

  const fetchBotDetails = async (botId) => {
    try {
      const response = await fetch(`/api/goal-bots/${botId}`, { credentials: 'include' })
      if (!response.ok) throw new Error('Failed to fetch bot details')
      const data = await response.json()
      setSelectedBotDetails(data)
      return data
    } catch (err) {
      console.error('Error fetching bot details:', err)
      setSelectedBotDetails(null)
      return null
    }
  }

  const createGoalBot = async (botData) => {
    try {
      const response = await fetch('/api/goal-bots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(botData),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail?.error || errorData.error || 'Failed to create goal bot')
      }

      const data = await response.json()
      if (toast) toast.success(`Created goal bot "${data.goal_bot.name}"`)
      await fetchGoalBots(false)
      return data.goal_bot
    } catch (err) {
      console.error('Error creating goal bot:', err)
      if (toast) toast.error(err.message)
      throw err
    }
  }

  const updateGoalBot = async (botId, updates) => {
    try {
      const response = await fetch(`/api/goal-bots/${botId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(updates),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail?.error || 'Failed to update goal bot')
      }

      const data = await response.json()
      if (toast) toast.success(`Updated goal bot "${data.goal_bot.name}"`)
      await fetchGoalBots(false)
      return data.goal_bot
    } catch (err) {
      console.error('Error updating goal bot:', err)
      if (toast) toast.error(err.message)
      throw err
    }
  }

  const deleteGoalBot = async (botId, botName) => {
    try {
      const response = await fetch(`/api/goal-bots/${botId}`, {
        method: 'DELETE',
        credentials: 'include',
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail?.error || 'Failed to delete goal bot')
      }

      if (toast) toast.success(`Deleted goal bot "${botName}"`)
      await fetchGoalBots(false)

      if (selectedBot && selectedBot.bot_id === botId) {
        setSelectedBot(null)
        setSelectedBotDetails(null)
      }
    } catch (err) {
      console.error('Error deleting goal bot:', err)
      if (toast) toast.error(err.message)
      throw err
    }
  }

  const toggleGoalBot = async (botId) => {
    try {
      const response = await fetch(`/api/goal-bots/${botId}/toggle`, {
        method: 'POST',
        credentials: 'include',
      })

      if (!response.ok) throw new Error('Failed to toggle goal bot')

      const data = await response.json()
      if (toast) toast.success(`Goal bot ${data.is_enabled ? 'enabled' : 'disabled'}`)
      await fetchGoalBots(false)
    } catch (err) {
      console.error('Error toggling goal bot:', err)
      if (toast) toast.error(err.message)
    }
  }

  const pauseGoalBot = async (botId) => {
    try {
      const response = await fetch(`/api/goal-bots/${botId}/pause`, {
        method: 'POST',
        credentials: 'include',
      })

      if (!response.ok) throw new Error('Failed to pause goal bot')
      if (toast) toast.success('Goal bot paused')
      await fetchGoalBots(false)
    } catch (err) {
      console.error('Error pausing goal bot:', err)
      if (toast) toast.error(err.message)
    }
  }

  const resumeGoalBot = async (botId) => {
    try {
      const response = await fetch(`/api/goal-bots/${botId}/resume`, {
        method: 'POST',
        credentials: 'include',
      })

      if (!response.ok) throw new Error('Failed to resume goal bot')
      if (toast) toast.success('Goal bot resumed')
      await fetchGoalBots(false)
    } catch (err) {
      console.error('Error resuming goal bot:', err)
      if (toast) toast.error(err.message)
    }
  }

  const triggerGoalBot = async (botId) => {
    try {
      const response = await fetch(`/api/goal-bots/${botId}/trigger`, {
        method: 'POST',
        credentials: 'include',
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail?.error || 'Failed to trigger goal bot')
      }

      const data = await response.json()
      if (toast) toast.success(`Triggered goal bot run (${data.run_id.slice(0, 8)}...)`)
      await fetchGoalBots(false)
      return data
    } catch (err) {
      console.error('Error triggering goal bot:', err)
      if (toast) toast.error(err.message)
      throw err
    }
  }

  const cancelGoalBot = async (botId) => {
    try {
      const response = await fetch(`/api/goal-bots/${botId}/cancel`, {
        method: 'POST',
        credentials: 'include',
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail?.error || 'No running job to cancel')
      }

      if (toast) toast.success('Goal bot run cancelled')
      await fetchGoalBots(false)
    } catch (err) {
      console.error('Error cancelling goal bot:', err)
      if (toast) toast.error(err.message)
    }
  }

  const fetchBotRuns = async (botId, page = 1) => {
    try {
      const response = await fetch(`/api/goal-bots/${botId}/runs?page=${page}&per_page=20`, {
        credentials: 'include',
      })
      if (!response.ok) throw new Error('Failed to fetch runs')
      return await response.json()
    } catch (err) {
      console.error('Error fetching bot runs:', err)
      return { runs: [], pagination: {} }
    }
  }

  const fetchRunDetails = async (botId, runId) => {
    try {
      const response = await fetch(`/api/goal-bots/${botId}/runs/${runId}`, {
        credentials: 'include',
      })
      if (!response.ok) throw new Error('Failed to fetch run details')
      return await response.json()
    } catch (err) {
      console.error('Error fetching run details:', err)
      return null
    }
  }

  const resetBotState = async (botId) => {
    try {
      const response = await fetch(`/api/goal-bots/${botId}/state`, {
        method: 'DELETE',
        credentials: 'include',
      })

      if (!response.ok) throw new Error('Failed to reset state')
      if (toast) toast.success('Bot state reset')
    } catch (err) {
      console.error('Error resetting bot state:', err)
      if (toast) toast.error(err.message)
    }
  }

  return {
    goalBots,
    loading,
    error,
    selectedBot,
    selectedBotDetails,
    showCreateModal,
    setSelectedBot,
    setShowCreateModal,
    fetchGoalBots,
    fetchBotDetails,
    createGoalBot,
    updateGoalBot,
    deleteGoalBot,
    toggleGoalBot,
    pauseGoalBot,
    resumeGoalBot,
    triggerGoalBot,
    cancelGoalBot,
    fetchBotRuns,
    fetchRunDetails,
    resetBotState,
  }
}
