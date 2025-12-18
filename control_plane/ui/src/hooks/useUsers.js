import { useState } from 'react'

export function useUsers(toast) {
  const [users, setUsers] = useState([])
  const [syncing, setSyncing] = useState(false)
  const [selectedUser, setSelectedUser] = useState(null)
  const [currentUserEmail, setCurrentUserEmail] = useState(null)

  const fetchUsers = async () => {
    try {
      const response = await fetch('/api/users')
      if (!response.ok) throw new Error('Failed to fetch users')
      const data = await response.json()
      setUsers(data.users || [])

      // Get current user email from session
      const meResponse = await fetch('/api/users/me')
      if (meResponse.ok) {
        const meData = await meResponse.json()
        setCurrentUserEmail(meData.email)
      }
    } catch (err) {
      console.error('Error fetching users:', err)
      setUsers([])
      if (toast) toast.error(`Failed to fetch users: ${err.message}`)
    }
  }

  const syncUsers = async () => {
    try {
      setSyncing(true)
      const response = await fetch('/api/users/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      })
      if (!response.ok) throw new Error('Failed to sync users')
      const data = await response.json()
      if (toast) toast.success(`Sync complete: ${data.stats.created} created, ${data.stats.updated} updated`)
      fetchUsers()
    } catch (err) {
      if (toast) toast.error(`Sync failed: ${err.message}`)
    } finally {
      setSyncing(false)
    }
  }

  const updateAdminStatus = async (userId, isAdmin) => {
    try {
      const response = await fetch(`/api/users/${userId}/admin`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_admin: isAdmin })
      })
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Failed to update admin status')
      }
      const data = await response.json()
      if (toast) toast.success(isAdmin ? `${data.user.email} is now an admin` : `Removed admin from ${data.user.email}`)
      fetchUsers()
    } catch (err) {
      if (toast) toast.error(`Failed to update admin status: ${err.message}`)
      throw err
    }
  }

  return {
    users,
    syncing,
    selectedUser,
    setSelectedUser,
    currentUserEmail,
    fetchUsers,
    syncUsers,
    updateAdminStatus,
  }
}
