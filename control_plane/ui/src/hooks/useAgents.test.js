/**
 * Tests for useAgents hook
 */

import { renderHook, act, waitFor } from '@testing-library/react'
import { useAgents } from './useAgents'

// Mock fetch
global.fetch = jest.fn()

describe('useAgents', () => {
  const mockToast = {
    success: jest.fn(),
    error: jest.fn(),
  }

  beforeEach(() => {
    fetch.mockClear()
    mockToast.success.mockClear()
    mockToast.error.mockClear()
  })

  describe('fetchAgents', () => {
    it('should fetch agents successfully', async () => {
      const mockAgents = [
        { name: 'test_agent', display_name: 'Test Agent', is_enabled: true }
      ]

      fetch.mockResolvedValue({
        ok: true,
        json: async () => ({ agents: mockAgents })
      })

      const { result } = renderHook(() => useAgents(mockToast))

      await act(async () => {
        await result.current.fetchAgents()
      })

      await waitFor(() => {
        expect(result.current.agents).toEqual(mockAgents)
      })
    })
  })

  describe('toggleAgent', () => {
    it('should include credentials in fetch call', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ is_enabled: false })
      })
      // Mock the subsequent fetchAgents call
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ agents: [] })
      })

      const { result } = renderHook(() => useAgents(mockToast))

      await act(async () => {
        await result.current.toggleAgent('test_agent')
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/agents/test_agent/toggle',
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
        })
      )
    })

    it('should show success toast on toggle', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ is_enabled: true })
      })
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ agents: [] })
      })

      const { result } = renderHook(() => useAgents(mockToast))

      await act(async () => {
        await result.current.toggleAgent('test_agent')
      })

      expect(mockToast.success).toHaveBeenCalledWith('Agent enabled')
    })

    it('should show error toast on toggle failure', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
      })

      const { result } = renderHook(() => useAgents(mockToast))

      await act(async () => {
        await result.current.toggleAgent('test_agent')
      })

      expect(mockToast.error).toHaveBeenCalled()
    })
  })

  describe('deleteAgent', () => {
    it('should include credentials in fetch call', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'deleted' })
      })
      // Mock the subsequent fetchAgents call
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ agents: [] })
      })

      const { result } = renderHook(() => useAgents(mockToast))

      await act(async () => {
        await result.current.deleteAgent('test_agent')
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/agents/test_agent',
        expect.objectContaining({
          method: 'DELETE',
          credentials: 'include',
        })
      )
    })

    it('should show success toast on delete', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'deleted' })
      })
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ agents: [] })
      })

      const { result } = renderHook(() => useAgents(mockToast))

      await act(async () => {
        await result.current.deleteAgent('test_agent')
      })

      expect(mockToast.success).toHaveBeenCalledWith('Agent "test_agent" has been deleted')
    })

    it('should show error toast on delete failure', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        json: async () => ({ error: 'Cannot delete system agent' })
      })

      const { result } = renderHook(() => useAgents(mockToast))

      await act(async () => {
        try {
          await result.current.deleteAgent('help')
        } catch (e) {
          // Expected to throw
        }
      })

      expect(mockToast.error).toHaveBeenCalledWith('Failed to delete agent: Cannot delete system agent')
    })
  })
})
