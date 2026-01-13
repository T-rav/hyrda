/**
 * Tests for useGroups hook
 */

import { renderHook, act, waitFor } from '@testing-library/react'
import { useGroups } from './useGroups'

// Mock fetch
global.fetch = jest.fn()

describe('useGroups', () => {
  const mockToast = {
    success: jest.fn(),
    error: jest.fn(),
  }

  const mockRefreshUsers = jest.fn()

  beforeEach(() => {
    fetch.mockClear()
    mockToast.success.mockClear()
    mockToast.error.mockClear()
    mockRefreshUsers.mockClear()
  })

  describe('fetchGroups', () => {
    it('should fetch groups successfully', async () => {
      const mockGroups = [
        { group_name: 'test_group', display_name: 'Test Group', user_count: 5 }
      ]

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ groups: mockGroups })
      })

      const { result } = renderHook(() => useGroups(mockToast, mockRefreshUsers))

      await act(async () => {
        await result.current.fetchGroups()
      })

      await waitFor(() => {
        expect(result.current.groups).toEqual(mockGroups)
      })
    })

    it('should handle fetch error', async () => {
      fetch.mockRejectedValueOnce(new Error('Network error'))

      const { result } = renderHook(() => useGroups(mockToast, mockRefreshUsers))

      await act(async () => {
        await result.current.fetchGroups()
      })

      // fetchGroups doesn't call toast.error, just console.error
      // Verify that groups is set to empty array on error
      expect(result.current.groups).toEqual([])
    })
  })

  describe('createGroup', () => {
    it('should create group successfully', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'created', group_name: 'new_group' })
      })

      const { result } = renderHook(() => useGroups(mockToast, mockRefreshUsers))

      await act(async () => {
        await result.current.createGroup({
          group_name: 'new_group',
          display_name: 'New Group',
          description: 'Test description'
        })
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/groups',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
      )
      expect(mockToast.success).toHaveBeenCalledWith('Group created successfully')
    })

    it('should handle create error', async () => {
      fetch.mockResolvedValueOnce({
        ok: false
      })

      const { result } = renderHook(() => useGroups(mockToast, mockRefreshUsers))

      await act(async () => {
        await result.current.createGroup({
          group_name: 'fail_group',
          display_name: 'Fail Group'
        })
      })

      expect(mockToast.error).toHaveBeenCalled()
    })
  })

  describe('updateGroup', () => {
    it('should update group successfully', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'updated',
          display_name: 'Updated Name'
        })
      })

      const { result } = renderHook(() => useGroups(mockToast, mockRefreshUsers))

      await act(async () => {
        await result.current.updateGroup('test_group', {
          display_name: 'Updated Name',
          description: 'Updated description'
        })
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/groups/test_group',
        expect.objectContaining({
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' }
        })
      )
      expect(mockToast.success).toHaveBeenCalledWith('Group updated successfully')
    })
  })

  describe('deleteGroup', () => {
    it('should delete group successfully', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'deleted' })
      })

      const { result } = renderHook(() => useGroups(mockToast, mockRefreshUsers))

      await act(async () => {
        await result.current.deleteGroup('test_group')
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/groups/test_group',
        expect.objectContaining({ method: 'DELETE' })
      )
      expect(mockToast.success).toHaveBeenCalledWith('Group deleted successfully')
      expect(mockRefreshUsers).toHaveBeenCalled()
    })

    it('should handle delete error for system group', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 403
      })

      const { result } = renderHook(() => useGroups(mockToast, mockRefreshUsers))

      await act(async () => {
        await result.current.deleteGroup('all_users')
      })

      expect(mockToast.error).toHaveBeenCalled()
    })
  })

  describe('addUserToGroup', () => {
    it('should add user to group successfully', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'added' })
      })

      const { result } = renderHook(() => useGroups(mockToast, mockRefreshUsers))

      await act(async () => {
        await result.current.addUserToGroup('test_group', 'U123')
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/groups/test_group/users',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: 'U123', added_by: 'admin' })
        })
      )
      expect(mockToast.success).toHaveBeenCalledWith('User added to group')
    })
  })

  describe('removeUserFromGroup', () => {
    it('should remove user from group successfully', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'removed' })
      })

      const { result } = renderHook(() => useGroups(mockToast, mockRefreshUsers))

      await act(async () => {
        await result.current.removeUserFromGroup('test_group', 'U123')
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/groups/test_group/users?user_id=U123',
        expect.objectContaining({ method: 'DELETE' })
      )
      expect(mockToast.success).toHaveBeenCalledWith('User removed from group')
    })
  })
})
