import { useState, useCallback } from 'react'

export function useUsers(toast) {
  const [users, setUsers] = useState([])
  const [totalUsers, setTotalUsers] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [selectedUser, setSelectedUser] = useState(null)
  const [currentUserEmail, setCurrentUserEmail] = useState(null)

  const INITIAL_PER_PAGE = 10
  const LOAD_MORE_COUNT = 50

  const fetchUsers = useCallback(async (page = 1, perPage = INITIAL_PER_PAGE, append = false) => {
    try {
      const response = await fetch(`/api/users?page=${page}&per_page=${perPage}`)
      if (!response.ok) throw new Error('Failed to fetch users')
      const data = await response.json()

      const newUsers = data.users || []
      const pagination = data.pagination || {}

      if (append) {
        setUsers(prev => [...prev, ...newUsers])
      } else {
        setUsers(newUsers)
      }

      setTotalUsers(pagination.total || newUsers.length)
      setCurrentPage(pagination.page || page)
      setHasMore(pagination.page < pagination.pages)

      // Get current user email from session
      const meResponse = await fetch('/api/users/me')
      if (meResponse.ok) {
        const meData = await meResponse.json()
        setCurrentUserEmail(meData.email)
      }
    } catch (err) {
      console.error('Error fetching users:', err)
      if (!append) {
        setUsers([])
        setTotalUsers(0)
      }
      if (toast) toast.error(`Failed to fetch users: ${err.message}`)
    }
  }, [toast])

  const loadMoreUsers = useCallback(async () => {
    if (loadingMore || !hasMore) return

    try {
      setLoadingMore(true)
      const nextPage = currentPage + 1
      const response = await fetch(`/api/users?page=${nextPage}&per_page=${LOAD_MORE_COUNT}`)
      if (!response.ok) throw new Error('Failed to load more users')
      const data = await response.json()

      const newUsers = data.users || []
      const pagination = data.pagination || {}

      setUsers(prev => [...prev, ...newUsers])
      setCurrentPage(pagination.page || nextPage)
      setHasMore(pagination.page < pagination.pages)
    } catch (err) {
      console.error('Error loading more users:', err)
      if (toast) toast.error(`Failed to load more users: ${err.message}`)
    } finally {
      setLoadingMore(false)
    }
  }, [currentPage, hasMore, loadingMore, toast])

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
      // Reset to first page after sync
      fetchUsers(1, INITIAL_PER_PAGE, false)
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
      // Update user in local state instead of refetching all
      setUsers(prev => prev.map(u =>
        u.slack_user_id === userId ? { ...u, is_admin: isAdmin } : u
      ))
    } catch (err) {
      if (toast) toast.error(`Failed to update admin status: ${err.message}`)
      throw err
    }
  }

  return {
    users,
    totalUsers,
    hasMore,
    loadingMore,
    syncing,
    selectedUser,
    setSelectedUser,
    currentUserEmail,
    fetchUsers,
    loadMoreUsers,
    syncUsers,
    updateAdminStatus,
  }
}
