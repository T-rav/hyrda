import React from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { vi } from 'vitest'
import ViewTaskModal from './ViewTaskModal'

// Mock the logger
vi.mock('../utils/logger', () => ({
  logError: vi.fn(),
}))

// Mock withBasePath to return path unchanged
vi.mock('../utils/tokenRefresh', () => ({
  withBasePath: (url) => url,
}))

// Mock fetch
global.fetch = vi.fn()

describe('ViewTaskModal', () => {
  const mockTaskTypes = [
    {
      type: 'youtube_ingest',
      name: 'YouTube Ingestion',
      description: 'Ingest YouTube videos',
      required_params: ['channel_url'],
      optional_params: ['include_videos', 'include_shorts'],
    },
  ]

  const mockTask = {
    id: 'test-job-123',
    name: 'My YouTube Task',
    trigger: "<class 'apscheduler.triggers.interval.IntervalTrigger'>",
    next_run_time: '2024-01-21T15:00:00Z',
    pending: false,
    args: [
      'youtube_ingest',
      {
        channel_url: 'https://youtube.com/@test',
        include_videos: true,
        include_shorts: false,
      },
    ],
    kwargs: {
      hours: 6,
      minutes: 0,
      seconds: 0,
    },
  }

  const mockOnClose = vi.fn()

  beforeEach(() => {
    fetch.mockClear()
    mockOnClose.mockClear()

    // Mock the task types API
    fetch.mockImplementation(() => {
      return Promise.resolve({
        json: () => Promise.resolve({ job_types: mockTaskTypes }),
      })
    })
  })

  it('renders the modal with task name', async () => {
    render(<ViewTaskModal task={mockTask} onClose={mockOnClose} />)

    await waitFor(() => {
      expect(screen.getByText('My YouTube Task')).toBeInTheDocument()
    })
  })

  it('displays task type', async () => {
    render(<ViewTaskModal task={mockTask} onClose={mockOnClose} />)

    await waitFor(() => {
      expect(screen.getByText('TASK TYPE')).toBeInTheDocument()
      expect(screen.getByText('youtube_ingest')).toBeInTheDocument()
    })
  })

  it('displays active status badge', async () => {
    render(<ViewTaskModal task={mockTask} onClose={mockOnClose} />)

    await waitFor(() => {
      expect(screen.getByText('STATUS')).toBeInTheDocument()
      expect(screen.getByText('Active')).toBeInTheDocument()
    })
  })

  it('displays paused status for inactive task', async () => {
    const pausedTask = {
      ...mockTask,
      next_run_time: null,
    }

    render(<ViewTaskModal task={pausedTask} onClose={mockOnClose} />)

    await waitFor(() => {
      // Look for the Paused badge specifically in the STATUS section
      const statusSection = screen.getByText('STATUS').closest('.p-3')
      expect(statusSection.textContent).toContain('Paused')
    })
  })

  it('displays next run time', async () => {
    render(<ViewTaskModal task={mockTask} onClose={mockOnClose} />)

    await waitFor(() => {
      expect(screen.getByText('NEXT RUN')).toBeInTheDocument()
    })

    // Check that the date is formatted and displayed
    const formattedDate = new Date('2024-01-21T15:00:00Z').toLocaleString()
    expect(screen.getByText(formattedDate)).toBeInTheDocument()
  })

  it('displays schedule description for interval trigger', async () => {
    render(<ViewTaskModal task={mockTask} onClose={mockOnClose} />)

    await waitFor(() => {
      expect(screen.getByText('SCHEDULE')).toBeInTheDocument()
      expect(screen.getByText('Every 6 hours')).toBeInTheDocument()
    })
  })

  it('displays task ID', async () => {
    render(<ViewTaskModal task={mockTask} onClose={mockOnClose} />)

    await waitFor(() => {
      expect(screen.getByText(/Task ID:/)).toBeInTheDocument()
      expect(screen.getByText('test-job-123')).toBeInTheDocument()
    })
  })

  it('renders TaskParameters component with readOnly=true', async () => {
    render(<ViewTaskModal task={mockTask} onClose={mockOnClose} />)

    await waitFor(() => {
      expect(screen.getByText('Task Parameters')).toBeInTheDocument()
      expect(screen.getByText('Channel URL')).toBeInTheDocument()
    })

    // Verify inputs are disabled (read-only mode)
    const inputs = screen.getAllByRole('textbox')
    inputs.forEach(input => {
      expect(input).toBeDisabled()
    })
  })

  it('calls onClose when close button is clicked', async () => {
    render(<ViewTaskModal task={mockTask} onClose={mockOnClose} />)

    await waitFor(() => {
      expect(screen.getByText('Close')).toBeInTheDocument()
    })

    const closeButton = screen.getByText('Close')
    fireEvent.click(closeButton)

    expect(mockOnClose).toHaveBeenCalled()
  })

  it('calls onClose when clicking overlay', async () => {
    render(<ViewTaskModal task={mockTask} onClose={mockOnClose} />)

    await waitFor(() => {
      expect(screen.getByText('My YouTube Task')).toBeInTheDocument()
    })

    const overlay = screen.getByText('My YouTube Task').closest('.modal-overlay')
    fireEvent.click(overlay)

    expect(mockOnClose).toHaveBeenCalled()
  })

  it('does not call onClose when clicking modal content', async () => {
    render(<ViewTaskModal task={mockTask} onClose={mockOnClose} />)

    await waitFor(() => {
      expect(screen.getByText('My YouTube Task')).toBeInTheDocument()
    })

    const modalContent = screen.getByText('My YouTube Task').closest('.modal-content')
    fireEvent.click(modalContent)

    expect(mockOnClose).not.toHaveBeenCalled()
  })

  it('handles task without next_run_time', async () => {
    const taskWithoutNextRun = {
      ...mockTask,
      next_run_time: null,
    }

    render(<ViewTaskModal task={taskWithoutNextRun} onClose={mockOnClose} />)

    await waitFor(() => {
      // Look for the NEXT RUN section showing 'Paused'
      const nextRunSection = screen.getByText('NEXT RUN').closest('.p-3')
      expect(nextRunSection.textContent).toContain('Paused')
    })
  })

  it('displays cron trigger description', async () => {
    const cronTask = {
      ...mockTask,
      trigger: "<class 'apscheduler.triggers.cron.CronTrigger'>",
      kwargs: {
        minute: '0',
        hour: '9',
        day: '*',
        month: '*',
        day_of_week: '1',
      },
    }

    render(<ViewTaskModal task={cronTask} onClose={mockOnClose} />)

    await waitFor(() => {
      expect(screen.getByText('Weekly (Monday 9:00 AM)')).toBeInTheDocument()
    })
  })

  it('displays daily cron trigger description', async () => {
    const dailyTask = {
      ...mockTask,
      trigger: "<class 'apscheduler.triggers.cron.CronTrigger'>",
      kwargs: {
        minute: '0',
        hour: '0',
        day: '*',
        month: '*',
        day_of_week: '*',
      },
    }

    render(<ViewTaskModal task={dailyTask} onClose={mockOnClose} />)

    await waitFor(() => {
      expect(screen.getByText('Daily at midnight')).toBeInTheDocument()
    })
  })
})
