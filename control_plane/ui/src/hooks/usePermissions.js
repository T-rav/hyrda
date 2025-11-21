import { useState } from 'react'

export function usePermissions(toast, refreshAgentDetails) {
  const [userPermissions, setUserPermissions] = useState([])

  const fetchUserPermissions = async (userId) => {
    try {
      const response = await fetch(`/api/users/${userId}/permissions`)
      if (!response.ok) throw new Error('Failed to fetch user permissions')
      const data = await response.json()
      setUserPermissions(data.agent_names || [])
    } catch (err) {
      console.error('Error fetching user permissions:', err)
      setUserPermissions([])
      if (toast) toast.error(`Failed to fetch permissions: ${err.message}`)
    }
  }

  const grantAgentToUser = async (userId, agentName) => {
    try {
      const response = await fetch(`/api/users/${userId}/permissions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_name: agentName, granted_by: 'admin' })
      })
      if (!response.ok) throw new Error('Failed to grant permission')
      if (toast) toast.success('Permission granted')
      // Refetch permissions to update UI
      fetchUserPermissions(userId)
    } catch (err) {
      if (toast) toast.error(`Failed to grant permission: ${err.message}`)
    }
  }

  const revokeAgentFromUser = async (userId, agentName) => {
    try {
      const response = await fetch(`/api/users/${userId}/permissions?agent_name=${agentName}`, {
        method: 'DELETE'
      })
      if (!response.ok) throw new Error('Failed to revoke permission')
      if (toast) toast.success('Permission revoked')
      // Refetch permissions to update UI
      fetchUserPermissions(userId)
    } catch (err) {
      if (toast) toast.error(`Failed to revoke permission: ${err.message}`)
    }
  }

  const grantAgentToGroup = async (groupName, agentName) => {
    try {
      const response = await fetch(`/api/groups/${groupName}/agents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_name: agentName, granted_by: 'admin' })
      })
      if (!response.ok) throw new Error('Failed to grant agent access')
      if (toast) toast.success('Agent access granted to group')
      // Refresh agent details to update UI
      if (refreshAgentDetails) refreshAgentDetails(agentName)
    } catch (err) {
      if (toast) toast.error(`Failed to grant access: ${err.message}`)
    }
  }

  const revokeAgentFromGroup = async (groupName, agentName) => {
    try {
      const response = await fetch(`/api/groups/${groupName}/agents?agent_name=${agentName}`, {
        method: 'DELETE'
      })
      if (!response.ok) throw new Error('Failed to revoke agent access')
      if (toast) toast.success('Agent access revoked from group')
      // Refresh agent details to update UI
      if (refreshAgentDetails) refreshAgentDetails(agentName)
    } catch (err) {
      if (toast) toast.error(`Failed to revoke access: ${err.message}`)
    }
  }

  return {
    userPermissions,
    fetchUserPermissions,
    grantAgentToUser,
    revokeAgentFromUser,
    grantAgentToGroup,
    revokeAgentFromGroup,
  }
}
