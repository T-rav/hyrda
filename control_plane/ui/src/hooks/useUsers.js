import { useState } from 'react'

export function useUsers(toast) {
  const [users, setUsers] = useState([])
  const [syncing, setSyncing] = useState(false)
  const [selectedUser, setSelectedUser] = useState(null)

  const fetchUsers = async () => {
    try {
      const response = await fetch('/api/users')
      if (!response.ok) throw new Error('Failed to fetch users')
      const data = await response.json()
      setUsers(data.users || [])
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

  return {
    users,
    syncing,
    selectedUser,
    setSelectedUser,
    fetchUsers,
    syncUsers,
  }
}
