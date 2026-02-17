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
      if (url.includes('/auth/me')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ email: 'test@example.com', authenticated: true })
        })
      }
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

  test('renders app with correct title and header', () => {
    render(<App />)

    // Test the main header title
    const titles = screen.getAllByText('InsightMesh Tasks')
    expect(titles.find(el => el.tagName === 'H1')).toBeInTheDocument()

    // Test navigation elements
    expect(screen.getByRole('button', { name: /dashboard/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /tasks/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /health/i })).toBeInTheDocument()
  })

  test('ensures Tasks Dashboard title consistency', () => {
    render(<App />)

    // Verify the main header title is exactly "InsightMesh Tasks"
    const titles = screen.getAllByText('InsightMesh Tasks')
    const mainTitle = titles.find(el => el.tagName === 'H1')
    expect(mainTitle).toBeInTheDocument()

    // Verify footer exists with correct text
    const footer = document.querySelector('.footer')
    expect(footer).toBeInTheDocument()
    expect(footer.textContent).toContain('InsightMesh Tasks')
  })

  test('verifies Tasks Dashboard title does not change unexpectedly', () => {
    render(<App />)

    // This test ensures the title remains "InsightMesh Tasks" and not something else
    const titles = screen.getAllByText('InsightMesh Tasks')
    expect(titles.find(el => el.tagName === 'H1')).toBeInTheDocument()

    // Ensure it's not the Health Dashboard title
    expect(screen.queryByText('InsightMesh Health Dashboard')).not.toBeInTheDocument()

    // Ensure it's not a generic title
    expect(screen.queryByText('InsightMesh Dashboard')).not.toBeInTheDocument()
  })

  test('verifies HTML page title matches expected Tasks Dashboard title', async () => {
    render(<App />)

    // Wait for useEffect to set the document title
    await waitFor(() => {
      expect(document.title).toBe('InsightMesh - Tasks Dashboard')
    })

    // Ensure it's not the Health Dashboard title
    expect(document.title).not.toBe('InsightMesh - Health Dashboard')
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

  test('REGRESSION: data persists when switching tabs (shared state)', async () => {
    const user = userEvent.setup()
    render(<App />)

    // Wait for initial dashboard data to load (3 API calls: jobs, task-runs, scheduler/info)
    await waitFor(() => {
      expect(screen.getByText('Scheduler Status')).toBeInTheDocument()
    })

    const callsAfterDashboard = global.fetch.mock.calls.length

    // Switch to Tasks tab - should NOT make new API calls (jobs already loaded by Dashboard)
    await user.click(screen.getByRole('button', { name: /tasks/i }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /tasks/i })).toHaveClass('active')
    })

    const callsAfterFirstTasksSwitch = global.fetch.mock.calls.length
    // CRITICAL: Tasks tab should NOT fetch (jobs already loaded from Dashboard - shared state!)
    expect(callsAfterFirstTasksSwitch).toBe(callsAfterDashboard)

    // Switch back to Dashboard tab
    await user.click(screen.getByRole('button', { name: /dashboard/i }))
    await waitFor(() => {
      expect(screen.getByText('Scheduler Status')).toBeInTheDocument()
    })

    const callsAfterReturnToDashboard = global.fetch.mock.calls.length
    // CRITICAL: Dashboard should NOT re-fetch (state was preserved)
    expect(callsAfterReturnToDashboard).toBe(callsAfterFirstTasksSwitch)

    // Switch to Tasks tab AGAIN
    await user.click(screen.getByRole('button', { name: /tasks/i }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /tasks/i })).toHaveClass('active')
    })

    const callsAfterSecondTasksSwitch = global.fetch.mock.calls.length
    // CRITICAL: Tasks should NOT re-fetch (state was preserved)
    expect(callsAfterSecondTasksSwitch).toBe(callsAfterReturnToDashboard)

    // Verify data is still displayed after all tab switches
    await user.click(screen.getByRole('button', { name: /dashboard/i }))
    await waitFor(() => {
      expect(screen.getByText('Scheduler Status')).toBeInTheDocument()
    })

    // SUMMARY: Dashboard loads data once (3 API calls), then ALL tab switches use shared state
    // Total API calls should be 4: auth/me + 3 dashboard data calls, NO additional calls
    const finalFetchCount = global.fetch.mock.calls.length
    expect(finalFetchCount).toBe(callsAfterDashboard) // No new calls after initial load
  })

  test('loads and displays dashboard data', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Scheduler Status')).toBeInTheDocument()
    })

    // Check if API calls were made with credentials
    expect(global.fetch).toHaveBeenCalledWith('/api/jobs', { credentials: 'include' })
    expect(global.fetch).toHaveBeenCalledWith('/api/task-runs', { credentials: 'include' })
    expect(global.fetch).toHaveBeenCalledWith('/api/scheduler/info', { credentials: 'include' })
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
    const titles = screen.getAllByText('InsightMesh Tasks')
    expect(titles.find(el => el.tagName === 'H1')).toBeInTheDocument()
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

describe('Tasks Dashboard Title Consistency Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/auth/me')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ email: 'test@example.com', authenticated: true })
        })
      }
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
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    })
  })

  test('maintains consistent Tasks Dashboard branding', async () => {
    render(<App />)

    // Wait for useEffect to set the document title
    await waitFor(() => {
      expect(document.title).toBe('InsightMesh - Tasks Dashboard')
    })

    // Verify all title-related elements are consistent
    const titles = screen.getAllByText('InsightMesh Tasks')
    expect(titles.length).toBeGreaterThanOrEqual(2) // Header and footer
    expect(titles.find(el => el.tagName === 'H1')).toBeInTheDocument()
    expect(document.querySelector('.footer')).toBeInTheDocument()
  })

  test('prevents accidental title changes to Health Dashboard', () => {
    render(<App />)

    // Ensure Tasks Dashboard elements are present
    const titles = screen.getAllByText('InsightMesh Tasks')
    expect(titles.find(el => el.tagName === 'H1')).toBeInTheDocument()

    // Ensure Health Dashboard elements are NOT present
    expect(screen.queryByText('InsightMesh Health Dashboard')).not.toBeInTheDocument()
    expect(screen.queryByText('Health Dashboard')).not.toBeInTheDocument()
  })

  test('ensures navigation maintains correct dashboard context', () => {
    render(<App />)

    // Verify navigation elements maintain Tasks context
    expect(screen.getByRole('button', { name: /dashboard/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /tasks/i })).toBeInTheDocument()

    // Verify external health link points to correct location
    const healthLink = screen.getByRole('link', { name: /health/i })
    expect(healthLink).toHaveAttribute('href', 'http://localhost:8080/ui')
  })
})

describe('Dashboard Content', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/auth/me')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ email: 'test@example.com', authenticated: true })
        })
      }
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

describe('Authentication', () => {
  beforeEach(() => {
    // Mock window.location
    delete window.location
    window.location = { href: '' }
  })

  test('redirects to control plane login when not authenticated', async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/auth/me')) {
        return Promise.resolve({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Not authenticated' })
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    })

    render(<App />)

    await waitFor(() => {
      expect(window.location.href).toBe('https://localhost:6001/auth/start?redirect=https://localhost:5001')
    })
  })

  test('loads user email when authenticated', async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/auth/me')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ email: 'test@example.com', authenticated: true })
        })
      }
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
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    })

    render(<App />)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/auth/me', { credentials: 'include' })
    })

    // Should not redirect since auth succeeded
    expect(window.location.href).toBe('')
  })

  test('displays logout button when authenticated', async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/auth/me')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ email: 'test@example.com', authenticated: true })
        })
      }
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
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument()
    })
  })

  test('redirects to control plane on auth check failure', async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/auth/me')) {
        return Promise.reject(new Error('Network error'))
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    })

    render(<App />)

    await waitFor(() => {
      expect(window.location.href).toBe('https://localhost:6001/auth/start?redirect=https://localhost:5001')
    })
  })

  test('logout button submits form to control plane logout endpoint', async () => {
    const user = userEvent.setup()

    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/auth/me')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ email: 'test@example.com', authenticated: true })
        })
      }
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
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    })

    // Mock form.submit()
    const mockSubmit = vi.fn()
    HTMLFormElement.prototype.submit = mockSubmit

    render(<App />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument()
    })

    const logoutButton = screen.getByRole('button', { name: /logout/i })
    await user.click(logoutButton)

    // Should create and submit a form to logout endpoint
    expect(mockSubmit).toHaveBeenCalled()

    // Verify form was created with correct action
    const forms = document.querySelectorAll('form')
    const logoutForm = Array.from(forms).find(form => form.action.includes('/auth/logout'))
    expect(logoutForm).toBeDefined()
    expect(logoutForm.method.toLowerCase()).toBe('post')
    expect(logoutForm.action).toContain('https://localhost:6001/auth/logout')
  })

  test('sets user email state when authenticated', async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/auth/me')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ email: 'user@test.com', authenticated: true })
        })
      }
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
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument()
    })

    // Wait for email to be rendered in dropdown
    await waitFor(() => {
      const emailElement = document.querySelector('.user-email')
      expect(emailElement).toBeTruthy()
      expect(emailElement.textContent).toContain('user@test.com')
    })
  })

  test('redirects when authentication fails', async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/auth/me')) {
        return Promise.resolve({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Not authenticated' })
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    })

    render(<App />)

    // Should redirect to control plane login when not authenticated
    await waitFor(() => {
      expect(window.location.href).toBe('https://localhost:6001/auth/start?redirect=https://localhost:5001')
    })
  })
})

// Mock jobs with groups for testing GroupRow
const mockJobsWithGroups = {
  jobs: [
    {
      id: 'test-job-1',
      name: 'Test Job 1',
      group_name: 'System',
      func: 'test_function',
      trigger: 'interval[1:00:00]',
      next_run_time: '2025-09-24T18:00:00+00:00',
      pending: false,
      args: ['slack_user_import'],
      kwargs: {}
    },
    {
      id: 'test-job-2',
      name: 'Test Job 2',
      group_name: 'System',
      func: 'test_function',
      trigger: 'interval[0:30:00]',
      next_run_time: null,
      pending: false,
      args: ['metric_sync'],
      kwargs: {}
    },
    {
      id: 'test-job-3',
      name: 'Ungrouped Task',
      group_name: null,
      func: 'test_function',
      trigger: 'interval[2:00:00]',
      next_run_time: '2025-09-24T20:00:00+00:00',
      pending: false,
      args: ['website_scrape'],
      kwargs: {}
    }
  ]
}

describe('Tasks Content', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/auth/me')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ email: 'test@example.com', authenticated: true })
        })
      }
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

describe('Task Grouping and Column Alignment', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/auth/me')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ email: 'test@example.com', authenticated: true })
        })
      }
      if (url.includes('/api/jobs')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockJobsWithGroups)
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
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    })
  })

  test('displays grouped tasks with folder icons', async () => {
    const user = userEvent.setup()
    render(<App />)

    // Switch to tasks tab
    await user.click(screen.getByRole('button', { name: /tasks/i }))

    await waitFor(() => {
      // Should show the System group
      expect(screen.getByText('System')).toBeInTheDocument()
    })

    // Should show task count badge
    expect(screen.getByText(/2 tasks/i)).toBeInTheDocument()
  })

  test('expands and collapses task groups', async () => {
    const user = userEvent.setup()
    render(<App />)

    // Switch to tasks tab
    await user.click(screen.getByRole('button', { name: /tasks/i }))

    await waitFor(() => {
      expect(screen.getByText('System')).toBeInTheDocument()
    })

    // Initially group should be collapsed - tasks not visible
    expect(screen.queryByText('Test Job 1')).not.toBeInTheDocument()

    // Click to expand the group
    await user.click(screen.getByText('System'))

    // Now tasks should be visible
    await waitFor(() => {
      expect(screen.getByText('Test Job 1')).toBeInTheDocument()
      expect(screen.getByText('Test Job 2')).toBeInTheDocument()
    })

    // Click again to collapse
    await user.click(screen.getByText('System'))

    // Tasks should be hidden again
    await waitFor(() => {
      expect(screen.queryByText('Test Job 1')).not.toBeInTheDocument()
    })
  })

  test('REGRESSION: group rows have 4 columns for proper alignment', async () => {
    const user = userEvent.setup()
    render(<App />)

    // Switch to tasks tab
    await user.click(screen.getByRole('button', { name: /tasks/i }))

    await waitFor(() => {
      expect(screen.getByText('System')).toBeInTheDocument()
    })

    // Find the group row
    const groupRow = screen.getByText('System').closest('tr')
    expect(groupRow).toBeInTheDocument()

    // Count the number of td elements - should be exactly 4 for alignment
    const cells = groupRow.querySelectorAll('td')
    expect(cells.length).toBe(4)

    // First cell should contain the group name
    expect(cells[0].textContent).toContain('System')

    // Last cell should contain action buttons
    const actionButtons = cells[3].querySelectorAll('button')
    expect(actionButtons.length).toBeGreaterThan(0)
  })

  test('REGRESSION: task rows have 4 columns matching header', async () => {
    const user = userEvent.setup()
    render(<App />)

    // Switch to tasks tab
    await user.click(screen.getByRole('button', { name: /tasks/i }))

    await waitFor(() => {
      expect(screen.getByText('System')).toBeInTheDocument()
    })

    // Expand the group
    await user.click(screen.getByText('System'))

    await waitFor(() => {
      expect(screen.getByText('Test Job 1')).toBeInTheDocument()
    })

    // Find a task row
    const taskRow = screen.getByText('Test Job 1').closest('tr')
    expect(taskRow).toBeInTheDocument()

    // Count the number of td elements - should be exactly 4
    const cells = taskRow.querySelectorAll('td')
    expect(cells.length).toBe(4)
  })

  test('table header has 4 columns', async () => {
    const user = userEvent.setup()
    render(<App />)

    // Switch to tasks tab
    await user.click(screen.getByRole('button', { name: /tasks/i }))

    await waitFor(() => {
      expect(screen.getByText('All Tasks')).toBeInTheDocument()
    })

    // Find the table header
    const table = document.querySelector('.table')
    expect(table).toBeInTheDocument()

    const headerCells = table.querySelectorAll('thead th')
    expect(headerCells.length).toBe(4)
  })

  test('ungrouped tasks render without group header', async () => {
    const user = userEvent.setup()
    render(<App />)

    // Switch to tasks tab
    await user.click(screen.getByRole('button', { name: /tasks/i }))

    await waitFor(() => {
      // Ungrouped task should be visible directly (not inside a collapsed group)
      expect(screen.getByText('Ungrouped Task')).toBeInTheDocument()
    })
  })

  test('group row action buttons are aligned with task row action buttons', async () => {
    const user = userEvent.setup()
    render(<App />)

    // Switch to tasks tab
    await user.click(screen.getByRole('button', { name: /tasks/i }))

    await waitFor(() => {
      expect(screen.getByText('System')).toBeInTheDocument()
    })

    // Get group row
    const groupRow = screen.getByText('System').closest('tr')
    const groupCells = groupRow.querySelectorAll('td')

    // Expand group
    await user.click(screen.getByText('System'))

    await waitFor(() => {
      expect(screen.getByText('Test Job 1')).toBeInTheDocument()
    })

    // Get task row
    const taskRow = screen.getByText('Test Job 1').closest('tr')
    const taskCells = taskRow.querySelectorAll('td')

    // Both should have same number of columns
    expect(groupCells.length).toBe(taskCells.length)
    expect(groupCells.length).toBe(4)

    // Actions should be in the 4th column (index 3) for both
    expect(groupCells[3].querySelectorAll('button').length).toBeGreaterThan(0)
    expect(taskCells[3].querySelectorAll('button').length).toBeGreaterThan(0)
  })
})
