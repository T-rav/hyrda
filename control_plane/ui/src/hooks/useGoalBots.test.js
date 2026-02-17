/**
 * Tests for useGoalBots hook
 */

import { renderHook, act, waitFor } from '@testing-library/react'
import { useGoalBots } from './useGoalBots'

// Mock fetch
global.fetch = jest.fn()

describe('useGoalBots', () => {
  const mockToast = {
    success: jest.fn(),
    error: jest.fn(),
  }

  beforeEach(() => {
    fetch.mockClear()
    mockToast.success.mockClear()
    mockToast.error.mockClear()
  })

  describe('fetchGoalBots', () => {
    it('should include credentials in fetch call', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ goal_bots: [] })
      })

      const { result } = renderHook(() => useGoalBots(mockToast))

      await act(async () => {
        await result.current.fetchGoalBots()
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/goal-bots',
        expect.objectContaining({
          credentials: 'include',
        })
      )
    })
  })

  describe('createGoalBot', () => {
    it('should include credentials in fetch call', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ goal_bot: { name: 'test_bot', bot_id: '123' } })
      })
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ goal_bots: [] })
      })

      const { result } = renderHook(() => useGoalBots(mockToast))

      await act(async () => {
        await result.current.createGoalBot({ name: 'test_bot', goal_prompt: 'Test' })
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/goal-bots',
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
        })
      )
    })
  })

  describe('updateGoalBot', () => {
    it('should include credentials in fetch call', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ goal_bot: { name: 'test_bot' } })
      })
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ goal_bots: [] })
      })

      const { result } = renderHook(() => useGoalBots(mockToast))

      await act(async () => {
        await result.current.updateGoalBot('123', { name: 'updated_bot' })
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/goal-bots/123',
        expect.objectContaining({
          method: 'PUT',
          credentials: 'include',
        })
      )
    })
  })

  describe('deleteGoalBot', () => {
    it('should include credentials in fetch call', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'deleted' })
      })
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ goal_bots: [] })
      })

      const { result } = renderHook(() => useGoalBots(mockToast))

      await act(async () => {
        await result.current.deleteGoalBot('123', 'test_bot')
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/goal-bots/123',
        expect.objectContaining({
          method: 'DELETE',
          credentials: 'include',
        })
      )
    })
  })

  describe('toggleGoalBot', () => {
    it('should include credentials in fetch call', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ is_enabled: false })
      })
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ goal_bots: [] })
      })

      const { result } = renderHook(() => useGoalBots(mockToast))

      await act(async () => {
        await result.current.toggleGoalBot('123')
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/goal-bots/123/toggle',
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
        })
      )
    })
  })

  describe('pauseGoalBot', () => {
    it('should include credentials in fetch call', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ is_paused: true })
      })
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ goal_bots: [] })
      })

      const { result } = renderHook(() => useGoalBots(mockToast))

      await act(async () => {
        await result.current.pauseGoalBot('123')
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/goal-bots/123/pause',
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
        })
      )
    })
  })

  describe('resumeGoalBot', () => {
    it('should include credentials in fetch call', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ is_paused: false })
      })
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ goal_bots: [] })
      })

      const { result } = renderHook(() => useGoalBots(mockToast))

      await act(async () => {
        await result.current.resumeGoalBot('123')
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/goal-bots/123/resume',
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
        })
      )
    })
  })

  describe('triggerGoalBot', () => {
    it('should include credentials in fetch call', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ run_id: 'run-123' })
      })
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ goal_bots: [] })
      })

      const { result } = renderHook(() => useGoalBots(mockToast))

      await act(async () => {
        await result.current.triggerGoalBot('123')
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/goal-bots/123/trigger',
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
        })
      )
    })
  })

  describe('cancelGoalBot', () => {
    it('should include credentials in fetch call', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'cancelled' })
      })
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ goal_bots: [] })
      })

      const { result } = renderHook(() => useGoalBots(mockToast))

      await act(async () => {
        await result.current.cancelGoalBot('123')
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/goal-bots/123/cancel',
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
        })
      )
    })
  })

  describe('fetchBotRuns', () => {
    it('should include credentials in fetch call', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ runs: [], pagination: {} })
      })

      const { result } = renderHook(() => useGoalBots(mockToast))

      await act(async () => {
        await result.current.fetchBotRuns('123')
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/goal-bots/123/runs?page=1&per_page=20',
        expect.objectContaining({
          credentials: 'include',
        })
      )
    })
  })

  describe('resetBotState', () => {
    it('should include credentials in fetch call', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'reset' })
      })

      const { result } = renderHook(() => useGoalBots(mockToast))

      await act(async () => {
        await result.current.resetBotState('123')
      })

      expect(fetch).toHaveBeenCalledWith(
        '/api/goal-bots/123/state',
        expect.objectContaining({
          method: 'DELETE',
          credentials: 'include',
        })
      )
    })
  })
})
