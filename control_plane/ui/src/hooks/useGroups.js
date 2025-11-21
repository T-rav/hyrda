import { useState } from 'react'

export function useGroups(toast, refreshUsers) {
  const [groups, setGroups] = useState([])
  const [showCreateGroup, setShowCreateGroup] = useState(false)
  const [selectedGroup, setSelectedGroup] = useState(null)

  const fetchGroups = async () => {
    try {
      const response = await fetch('/api/groups')
      if (!response.ok) throw new Error('Failed to fetch groups')
      const data = await response.json()
      setGroups(data.groups || [])
    } catch (err) {
      console.error('Error fetching groups:', err)
      setGroups([])
    }
  }

  const createGroup = async (groupData) => {
    try {
      const response = await fetch('/api/groups', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(groupData)
      })
      if (!response.ok) throw new Error('Failed to create group')
      fetchGroups()
      setShowCreateGroup(false)
      if (toast) toast.success('Group created successfully')
    } catch (err) {
      if (toast) toast.error(`Failed to create group: ${err.message}`)
    }
  }

  const addUserToGroup = async (groupName, userId) => {
    try {
      const response = await fetch(`/api/groups/${groupName}/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, added_by: 'admin' })
      })
      if (!response.ok) throw new Error('Failed to add user')
      fetchGroups()
      if (refreshUsers) refreshUsers()
      if (toast) toast.success('User added to group')
    } catch (err) {
      if (toast) toast.error(`Failed to add user: ${err.message}`)
    }
  }

  const removeUserFromGroup = async (groupName, userId) => {
    try {
      const response = await fetch(`/api/groups/${groupName}/users?user_id=${userId}`, {
        method: 'DELETE'
      })
      if (!response.ok) throw new Error('Failed to remove user')
      fetchGroups()
      if (refreshUsers) refreshUsers()
      if (toast) toast.success('User removed from group')
    } catch (err) {
      if (toast) toast.error(`Failed to remove user: ${err.message}`)
    }
  }

  return {
    groups,
    showCreateGroup,
    selectedGroup,
    setShowCreateGroup,
    setSelectedGroup,
    fetchGroups,
    createGroup,
    addUserToGroup,
    removeUserFromGroup,
  }
}
