import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useTasksData } from './useTasksData'

describe('useTasksData', () => {
  let fetchMock

  beforeEach(() => {
    fetchMock = vi.fn()
    global.fetch = fetchMock
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('REGRESSION TEST: credentials must always be included', () => {
    it('CRITICAL: all fetch calls MUST include credentials to prevent auth failures', async () => {
      // Mock all 4 API calls that refreshData makes
      fetchMock
        .mockResolvedValue({ ok: true, json: async () => ({}) })

      const { result } = renderHook(() => useTasksData())

      await act(async () => {
        await result.current.refreshData()
      })

      // CRITICAL: Every single fetch call must include credentials: 'include'
      // This regression test ensures we never break authentication again
      const calls = fetchMock.mock.calls

      // Verify we made 4 calls (scheduler, jobs, task-runs, metrics)
      expect(calls.length).toBeGreaterThanOrEqual(4)

      // Check ALL calls include credentials
      calls.forEach((call, index) => {
        const [url, options] = call
        expect(
          options,
          `Fetch call ${index} to ${url} is missing credentials: 'include'`
        ).toHaveProperty('credentials', 'include')
      })
    })

    it('should include credentials in task action API calls (pause)', async () => {
      fetchMock
        .mockResolvedValue({ ok: true, json: async () => ({}) })

      const { result } = renderHook(() => useTasksData())

      await act(async () => {
        await result.current.pauseTask('test-job-id')
      })

      // Find the pause API call
      const pauseCall = fetchMock.mock.calls.find(
        call => call[0] === '/api/jobs/test-job-id/pause'
      )

      expect(pauseCall).toBeDefined()
      expect(pauseCall[1]).toHaveProperty('method', 'POST')
      expect(pauseCall[1]).toHaveProperty('credentials', 'include')
    })

    it('should include credentials in task action API calls (resume)', async () => {
      fetchMock
        .mockResolvedValue({ ok: true, json: async () => ({}) })

      const { result } = renderHook(() => useTasksData())

      await act(async () => {
        await result.current.resumeTask('test-job-id')
      })

      // Find the resume API call
      const resumeCall = fetchMock.mock.calls.find(
        call => call[0] === '/api/jobs/test-job-id/resume'
      )

      expect(resumeCall).toBeDefined()
      expect(resumeCall[1]).toHaveProperty('method', 'POST')
      expect(resumeCall[1]).toHaveProperty('credentials', 'include')
    })

    it('should include credentials in task action API calls (delete)', async () => {
      fetchMock
        .mockResolvedValue({ ok: true, json: async () => ({}) })

      const { result } = renderHook(() => useTasksData())

      await act(async () => {
        await result.current.deleteTask('test-job-id')
      })

      // Find the delete API call
      const deleteCall = fetchMock.mock.calls.find(
        call => call[0] === '/api/jobs/test-job-id'
      )

      expect(deleteCall).toBeDefined()
      expect(deleteCall[1]).toHaveProperty('method', 'DELETE')
      expect(deleteCall[1]).toHaveProperty('credentials', 'include')
    })
  })

  describe('refreshData functionality', () => {
    it('should load all data sources in parallel', async () => {
      fetchMock
        .mockResolvedValueOnce({ ok: true, json: async () => ({ running: true }) })
        .mockResolvedValueOnce({ ok: true, json: async () => ({ jobs: [{ id: '1' }] }) })
        .mockResolvedValueOnce({ ok: true, json: async () => ({ task_runs: [{ id: 'r1' }], pagination: { total: 1 } }) })
        .mockResolvedValueOnce({ ok: true, json: async () => ({ rag_performance: { queries: 100 } }) })

      const { result } = renderHook(() => useTasksData())

      await act(async () => {
        await result.current.refreshData()
      })

      // Verify all 4 API calls were made
      expect(fetchMock).toHaveBeenCalledTimes(4)

      // Verify data was loaded
      expect(result.current.schedulerData).toEqual({ running: true })
      expect(result.current.tasksData).toEqual([{ id: '1' }])
      expect(result.current.taskRunsData).toEqual([{ id: 'r1' }])
      expect(result.current.taskRunsTotal).toEqual(1)
      expect(result.current.ragMetrics).toEqual({ queries: 100 })
    })

    it('should pass pagination parameters to task-runs endpoint', async () => {
      fetchMock
        .mockResolvedValueOnce({ ok: true, json: async () => ({ running: true }) })
        .mockResolvedValueOnce({ ok: true, json: async () => ({ jobs: [{ id: '1' }] }) })
        .mockResolvedValueOnce({ ok: true, json: async () => ({ task_runs: [{ id: 'r1' }], pagination: { total: 50 } }) })
        .mockResolvedValueOnce({ ok: true, json: async () => ({ rag_performance: { queries: 100 } }) })

      const { result } = renderHook(() => useTasksData())

      await act(async () => {
        await result.current.refreshData(2, 100)
      })

      // Find the task-runs call
      const taskRunsCall = fetchMock.mock.calls.find(
        call => call[0].includes('/task-runs')
      )

      expect(taskRunsCall).toBeDefined()
      expect(taskRunsCall[0]).toContain('page=2')
      expect(taskRunsCall[0]).toContain('per_page=100')
    })

    it('should set total from pagination response', async () => {
      fetchMock
        .mockResolvedValueOnce({ ok: true, json: async () => ({ running: true }) })
        .mockResolvedValueOnce({ ok: true, json: async () => ({ jobs: [{ id: '1' }] }) })
        .mockResolvedValueOnce({ ok: true, json: async () => ({ task_runs: [{ id: 'r1' }], pagination: { total: 4647 } }) })
        .mockResolvedValueOnce({ ok: true, json: async () => ({ rag_performance: { queries: 100 } }) })

      const { result } = renderHook(() => useTasksData())

      await act(async () => {
        await result.current.refreshData()
      })

      expect(result.current.taskRunsTotal).toEqual(4647)
    })

  })
})
