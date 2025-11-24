import { useState } from 'react'

export function useAgents(toast) {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [selectedAgentDetails, setSelectedAgentDetails] = useState(null)
  const [usageStats, setUsageStats] = useState({})

  const fetchUsageStats = async (agentNames) => {
    try {
      // Fetch usage for all agents
      const stats = {}
      await Promise.all(
        agentNames.map(async (name) => {
          try {
            const response = await fetch(`/api/agents/${name}/usage`)
            if (response.ok) {
              const data = await response.json()
              stats[name] = data
            }
          } catch (err) {
            // Silently fail for individual agents
            console.warn(`Failed to fetch usage for ${name}:`, err)
          }
        })
      )
      setUsageStats(stats)
    } catch (err) {
      console.error('Error fetching usage stats:', err)
    }
  }

  const fetchAgents = async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true)
      const response = await fetch('/api/agents')
      if (!response.ok) throw new Error('Failed to fetch agents')
      const data = await response.json()
      setAgents(data.agents || [])
      setError(null)

      // Fetch usage stats for all agents
      const agentNames = (data.agents || []).map(a => a.name)
      await fetchUsageStats(agentNames)
    } catch (err) {
      setError(err.message)
    } finally {
      if (showLoading) setLoading(false)
    }
  }

  const refreshAgents = async () => {
    // Force refresh without showing loading spinner
    await fetchAgents(false)
  }

  const fetchAgentDetails = async (agentName) => {
    try {
      const response = await fetch(`/api/agents/${agentName}`)
      if (!response.ok) throw new Error('Failed to fetch agent details')
      const data = await response.json()
      setSelectedAgentDetails(data)
    } catch (err) {
      console.error('Error fetching agent details:', err)
      setSelectedAgentDetails(null)
    }
  }

  const toggleAgent = async (agentName) => {
    try {
      const response = await fetch(`/api/agents/${agentName}/toggle`, {
        method: 'POST',
      })
      if (!response.ok) throw new Error('Failed to toggle agent')
      const data = await response.json()

      if (toast) {
        toast.success(`Agent ${data.is_enabled ? 'enabled' : 'disabled'}`)
      }

      // Refresh agent list to show new state
      await fetchAgents()

      // Also refresh agent details if currently viewing this agent
      if (selectedAgent && selectedAgent.name === agentName) {
        await fetchAgentDetails(agentName)
      }
    } catch (err) {
      console.error('Error toggling agent:', err)
      if (toast) toast.error(`Failed to toggle agent: ${err.message}`)
    }
  }

  return {
    agents,
    loading,
    error,
    selectedAgent,
    selectedAgentDetails,
    usageStats,
    setSelectedAgent,
    fetchAgents,
    refreshAgents,
    fetchAgentDetails,
    toggleAgent,
  }
}
