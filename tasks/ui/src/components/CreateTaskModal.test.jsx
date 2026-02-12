import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import CreateTaskModal from './CreateTaskModal'

// Mock the logger
vi.mock('../utils/logger', () => ({
  logError: vi.fn(),
}))

// Mock fetch
global.fetch = vi.fn()

describe('CreateTaskModal', () => {
  const mockTaskTypes = [
    {
      type: 'youtube_ingest',
      name: 'YouTube Ingestion',
      description: 'Ingest YouTube videos',
      required_params: ['channel_url'],
      optional_params: ['include_videos', 'include_shorts'],
    },
    {
      type: 'gdrive_ingest',
      name: 'Google Drive Ingestion',
      description: 'Ingest Google Drive files',
      required_params: ['folder_id'],
      optional_params: ['recursive'],
    },
  ]

  const mockOnClose = vi.fn()
  const mockOnTaskCreated = vi.fn()

  beforeEach(() => {
    fetch.mockClear()
    mockOnClose.mockClear()
    mockOnTaskCreated.mockClear()

    // Mock the task types API
    fetch.mockImplementation((url) => {
      if (url === '/api/job-types') {
        return Promise.resolve({
          json: () => Promise.resolve({ job_types: mockTaskTypes }),
        })
      }
      if (url === '/api/credentials') {
        return Promise.resolve({
          json: () => Promise.resolve({ credentials: [] }),
        })
      }
      return Promise.resolve({
        json: () => Promise.resolve({}),
      })
    })
  })

  it('renders the modal with title', async () => {
    render(
      <CreateTaskModal onClose={mockOnClose} onTaskCreated={mockOnTaskCreated} />
    )

    await waitFor(() => {
      expect(screen.getByText('Create New Task')).toBeInTheDocument()
    })
  })

  it('loads and displays task types', async () => {
    render(
      <CreateTaskModal onClose={mockOnClose} onTaskCreated={mockOnTaskCreated} />
    )

    await waitFor(() => {
      expect(screen.getByText('YouTube Ingestion - Ingest YouTube videos')).toBeInTheDocument()
      expect(screen.getByText('Google Drive Ingestion - Ingest Google Drive files')).toBeInTheDocument()
    })
  })

  it('calls onClose when close button is clicked', async () => {
    render(
      <CreateTaskModal onClose={mockOnClose} onTaskCreated={mockOnTaskCreated} />
    )

    await waitFor(() => {
      expect(screen.getByText('Create New Task')).toBeInTheDocument()
    })

    const closeButton = screen.getByText('Cancel')
    fireEvent.click(closeButton)

    expect(mockOnClose).toHaveBeenCalled()
  })

  it('shows schedule presets for interval trigger', async () => {
    render(
      <CreateTaskModal onClose={mockOnClose} onTaskCreated={mockOnTaskCreated} />
    )

    await waitFor(() => {
      expect(screen.getByText('Create New Task')).toBeInTheDocument()
    })

    // Interval is default, check for presets
    expect(screen.getByText('15 min')).toBeInTheDocument()
    expect(screen.getByText('1 hour')).toBeInTheDocument()
    expect(screen.getByText('24 hours')).toBeInTheDocument()
  })

  it('switches to cron trigger and shows presets', async () => {
    render(
      <CreateTaskModal onClose={mockOnClose} onTaskCreated={mockOnTaskCreated} />
    )

    await waitFor(() => {
      expect(screen.getByText('Create New Task')).toBeInTheDocument()
    })

    const triggerSelect = screen.getByDisplayValue('Interval')
    fireEvent.change(triggerSelect, { target: { value: 'cron' } })

    await waitFor(() => {
      expect(screen.getByText('Hourly')).toBeInTheDocument()
      expect(screen.getByText('Daily at midnight')).toBeInTheDocument()
    })
  })

  it('applies schedule preset when clicked', async () => {
    render(
      <CreateTaskModal onClose={mockOnClose} onTaskCreated={mockOnTaskCreated} />
    )

    await waitFor(() => {
      expect(screen.getByText('Create New Task')).toBeInTheDocument()
    })

    const presetButton = screen.getByText('6 hours')
    fireEvent.click(presetButton)

    const hoursInput = screen.getByLabelText('Hours')
    expect(hoursInput).toHaveValue(6)
  })


})
