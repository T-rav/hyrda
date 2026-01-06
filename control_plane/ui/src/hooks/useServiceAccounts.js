import { useState, useCallback } from 'react'

/**
 * Hook for managing service accounts (external API integrations).
 *
 * Provides CRUD operations for service accounts with API keys.
 */
export function useServiceAccounts(toast) {
  const [serviceAccounts, setServiceAccounts] = useState([])
  const [loading, setLoading] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createdApiKey, setCreatedApiKey] = useState(null) // Store API key after creation

  /**
   * Fetch all service accounts from API.
   */
  const fetchServiceAccounts = useCallback(async (includeRevoked = false) => {
    setLoading(true)
    try {
      const response = await fetch(
        `/api/service-accounts?include_revoked=${includeRevoked}`,
        { credentials: 'include' }
      )

      if (!response.ok) {
        throw new Error(`Failed to fetch service accounts: ${response.statusText}`)
      }

      const data = await response.json()
      setServiceAccounts(data)
      return data
    } catch (error) {
      console.error('Error fetching service accounts:', error)
      toast.error(`Failed to load service accounts: ${error.message}`)
      return []
    } finally {
      setLoading(false)
    }
  }, [toast])

  /**
   * Create a new service account.
   */
  const createServiceAccount = useCallback(async (accountData) => {
    setLoading(true)
    try {
      const response = await fetch('/api/service-accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(accountData),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to create service account')
      }

      const newAccount = await response.json()

      // Store the API key (only shown once!)
      setCreatedApiKey(newAccount.api_key)

      // Refresh the list
      await fetchServiceAccounts()

      toast.success(`Service account "${accountData.name}" created successfully!`)
      return newAccount
    } catch (error) {
      console.error('Error creating service account:', error)
      toast.error(`Failed to create service account: ${error.message}`)
      throw error
    } finally {
      setLoading(false)
    }
  }, [toast, fetchServiceAccounts])

  /**
   * Update a service account.
   */
  const updateServiceAccount = useCallback(async (accountId, updates) => {
    setLoading(true)
    try {
      const response = await fetch(`/api/service-accounts/${accountId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(updates),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to update service account')
      }

      await fetchServiceAccounts()
      toast.success('Service account updated successfully')
    } catch (error) {
      console.error('Error updating service account:', error)
      toast.error(`Failed to update service account: ${error.message}`)
      throw error
    } finally {
      setLoading(false)
    }
  }, [toast, fetchServiceAccounts])

  /**
   * Revoke a service account (cannot be undone).
   */
  const revokeServiceAccount = useCallback(async (accountId, reason = 'Revoked by admin') => {
    if (!confirm('Are you sure? This cannot be undone. The API key will be permanently disabled.')) {
      return
    }

    setLoading(true)
    try {
      const response = await fetch(`/api/service-accounts/${accountId}/revoke`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ reason }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to revoke service account')
      }

      await fetchServiceAccounts()
      toast.success('Service account revoked')
    } catch (error) {
      console.error('Error revoking service account:', error)
      toast.error(`Failed to revoke service account: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }, [toast, fetchServiceAccounts])

  /**
   * Delete a service account permanently.
   */
  const deleteServiceAccount = useCallback(async (accountId, accountName) => {
    if (!confirm(`Permanently delete "${accountName}"? This cannot be undone. (Prefer revoke for audit trail)`)) {
      return
    }

    setLoading(true)
    try {
      const response = await fetch(`/api/service-accounts/${accountId}`, {
        method: 'DELETE',
        credentials: 'include',
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to delete service account')
      }

      await fetchServiceAccounts()
      toast.success(`Service account "${accountName}" deleted`)
    } catch (error) {
      console.error('Error deleting service account:', error)
      toast.error(`Failed to delete service account: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }, [toast, fetchServiceAccounts])

  /**
   * Toggle active/inactive status.
   */
  const toggleActiveStatus = useCallback(async (accountId, currentStatus) => {
    await updateServiceAccount(accountId, { is_active: !currentStatus })
  }, [updateServiceAccount])

  return {
    serviceAccounts,
    loading,
    showCreateModal,
    createdApiKey,
    setShowCreateModal,
    setCreatedApiKey,
    fetchServiceAccounts,
    createServiceAccount,
    updateServiceAccount,
    revokeServiceAccount,
    deleteServiceAccount,
    toggleActiveStatus,
  }
}
