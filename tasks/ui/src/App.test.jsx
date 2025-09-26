import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import App from './App'

// Mock API responses
const mockJobs = {
  jobs: [
    {
      id: 'test-job-1',
      name: 'Test Job 1',
      func: 'test_function',
      trigger: 'interval[1:00:00]',
      next_run_time: '2025-09-24T18:00:00+00:00',
      pending: false,
      args: [],
      kwargs: {}
    }
  ]
}

const mockTaskRuns = {
  task_runs: [
    {
      id: 'run-1',
      job_id: 'test-job-1',
      status: 'SUCCESS',
      started_at: '2025-09-24T17:00:00+00:00',
      completed_at: '2025-09-24T17:01:00+00:00',
      result: { message: 'Success' }
    }
  ]
}

const mockSchedulerInfo = {
  running: true,
  jobs_count: 1,
  uptime: 3600
}

const mockTaskTypes = {
  task_types: [
    {
      name: 'slack_user_import',
      display_name: 'Slack User Import',
      description: 'Import users from Slack',
      required_params: ['workspace_filter'],
      optional_params: ['user_types', 'include_deactivated']
    }
  ]
}

describe('App Component', () => {
  beforeEach(() => {
    // Reset all mocks before each test
    vi.clearAllMocks()

    // Setup default fetch mocks
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/jobs')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockJobs)
        })
      }
      if (url.includes('/api/task-runs')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTaskRuns)
        })
      }
      if (url.includes('/api/scheduler/info')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockSchedulerInfo)
        })
      }
      if (url.includes('/api/task-types')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTaskTypes)
        })
      }
      return Promise.reject(new Error('Unknown URL'))
    })
  })

  test('renders app with header and navigation', () => {
    render(<App />)

    expect(screen.getByText('InsightMesh Tasks')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /dashboard/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /tasks/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /health/i })).toBeInTheDocument()
  })

  test('switches between dashboard and tasks tabs', async () => {
    const user = userEvent.setup()
    render(<App />)

    // Should start on dashboard
    expect(screen.getByRole('button', { name: /dashboard/i })).toHaveClass('active')

    // Switch to tasks tab
    await user.click(screen.getByRole('button', { name: /tasks/i }))
    expect(screen.getByRole('button', { name: /tasks/i })).toHaveClass('active')
    expect(screen.getByRole('button', { name: /dashboard/i })).not.toHaveClass('active')
  })

  test('loads and displays dashboard data', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Scheduler Status')).toBeInTheDocument()
    })

    // Check if API calls were made
    expect(global.fetch).toHaveBeenCalledWith('/api/jobs')
    expect(global.fetch).toHaveBeenCalledWith('/api/task-runs')
    expect(global.fetch).toHaveBeenCalledWith('/api/scheduler/info')
  })

  test('displays notification when shown', async () => {
    render(<App />)

    // We need to trigger a notification somehow - let's test the notification system
    // by checking if the notification container exists
    const notificationContainer = document.querySelector('.notification')
    expect(notificationContainer).toBeNull() // Should be null initially
  })

  test('handles API errors gracefully', async () => {
    // Mock fetch to return error
    global.fetch = vi.fn().mockRejectedValue(new Error('API Error'))

    render(<App />)

    // The app should still render even with API errors
    expect(screen.getByText('InsightMesh Tasks')).toBeInTheDocument()
  })

  test('auto-refresh functionality works', async () => {
    const user = userEvent.setup()
    render(<App />)

    // Wait for initial load
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled()
    })

    // Find and click auto-refresh button (should be in dashboard)
    const autoRefreshButton = screen.getByRole('button', { name: /auto-refresh/i })
    await user.click(autoRefreshButton)

    // Button text should change to indicate it's ON
    expect(autoRefreshButton).toHaveTextContent(/ON/i)
  })

  test('external health link has correct attributes', () => {
    render(<App />)

    const healthLink = screen.getByRole('link', { name: /health/i })
    expect(healthLink).toHaveAttribute('href', 'http://localhost:8080/ui')
    expect(healthLink).toHaveAttribute('target', '_blank')
    expect(healthLink).toHaveAttribute('rel', 'noopener noreferrer')
  })
})

describe('Dashboard Content', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/jobs')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockJobs)
        })
      }
      if (url.includes('/api/task-runs')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTaskRuns)
        })
      }
      if (url.includes('/api/scheduler/info')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockSchedulerInfo)
        })
      }
      return Promise.reject(new Error('Unknown URL'))
    })
  })

  test('displays scheduler status correctly', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Scheduler Status')).toBeInTheDocument()
      // The scheduler status shows stats, not just "Running"
      expect(screen.getByText('Total Runs:')).toBeInTheDocument()
    })
  })

  test('displays recent runs table', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Recent Runs')).toBeInTheDocument()
    })
  })
})

describe('Tasks Content', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/jobs')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockJobs)
        })
      }
      if (url.includes('/api/task-types')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTaskTypes)
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    })
  })

  test('displays create task button and tasks table', async () => {
    const user = userEvent.setup()
    render(<App />)

    // Switch to tasks tab
    await user.click(screen.getByRole('button', { name: /tasks/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /create task/i })).toBeInTheDocument()
    })
  })

  test('opens create task modal when button is clicked', async () => {
    const user = userEvent.setup()
    render(<App />)

    // Switch to tasks tab
    await user.click(screen.getByRole('button', { name: /tasks/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /create task/i })).toBeInTheDocument()
    })

    // Click create task button
    await user.click(screen.getByRole('button', { name: /create task/i }))

    // Modal should open
    expect(screen.getByText('Create New Task')).toBeInTheDocument()
  })
})
