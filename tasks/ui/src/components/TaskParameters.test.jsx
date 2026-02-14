import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import TaskParameters from './TaskParameters'

// Mock the logger
vi.mock('../utils/logger', () => ({
  logError: vi.fn(),
}))

// Mock fetch for credentials
global.fetch = vi.fn()

describe('TaskParameters', () => {
  const mockTaskTypes = [
    {
      type: 'test_job',
      name: 'Test Job',
      required_params: ['channel_url'],
      optional_params: ['include_videos', 'include_shorts', 'max_videos'],
    },
    {
      type: 'gdrive_ingest',
      name: 'Google Drive Ingestion',
      required_params: ['folder_id'],
      optional_params: ['recursive', 'force_update'],
    },
  ]

  beforeEach(() => {
    fetch.mockClear()
  })

  it('renders message when no task type is selected', () => {
    render(<TaskParameters taskType="" taskTypes={[]} />)

    expect(screen.getByText('Parameters will appear here based on the selected task type')).toBeInTheDocument()
  })

  it('renders required and optional parameters', () => {
    render(
      <TaskParameters
        taskType="test_job"
        taskTypes={mockTaskTypes}
      />
    )

    expect(screen.getByText('Required Parameters:')).toBeInTheDocument()
    expect(screen.getByText('Channel URL')).toBeInTheDocument()
    expect(screen.getByText('Optional Parameters:')).toBeInTheDocument()
  })

  it('renders boolean parameters as toggle switches', () => {
    render(
      <TaskParameters
        taskType="test_job"
        taskTypes={mockTaskTypes}
      />
    )

    // YouTube boolean toggles should be present
    expect(screen.getByText('Include Videos')).toBeInTheDocument()
    expect(screen.getByText('Include Shorts')).toBeInTheDocument()
  })

  it('renders in read-only mode with values displayed', () => {
    const values = {
      channel_url: 'https://youtube.com/@test',
      include_videos: true,
      include_shorts: false,
      max_videos: 50,
    }

    render(
      <TaskParameters
        taskType="test_job"
        taskTypes={mockTaskTypes}
        values={values}
        readOnly={true}
      />
    )

    // Values should be displayed in disabled inputs
    expect(screen.getByDisplayValue('https://youtube.com/@test')).toBeInTheDocument()
    expect(screen.getByDisplayValue('50')).toBeInTheDocument()

    // Toggles should be disabled
    const toggles = screen.getAllByRole('checkbox')
    toggles.forEach(toggle => {
      expect(toggle).toBeDisabled()
    })
  })

  it('calls onChange when parameter value changes', () => {
    const handleChange = vi.fn()
    render(
      <TaskParameters
        taskType="test_job"
        taskTypes={mockTaskTypes}
        onChange={handleChange}
      />
    )

    const urlInput = screen.getByPlaceholderText('https://www.youtube.com/@ChannelName')
    fireEvent.change(urlInput, { target: { value: 'https://youtube.com/@newchannel' } })

    expect(handleChange).toHaveBeenCalledWith('channel_url', 'https://youtube.com/@newchannel')
  })

  it('calls onChange when boolean toggle changes', () => {
    const handleChange = vi.fn()
    render(
      <TaskParameters
        taskType="test_job"
        taskTypes={mockTaskTypes}
        onChange={handleChange}
      />
    )

    // Find the Include Shorts toggle (initially unchecked)
    const shortsToggle = screen.getByLabelText('Include Shorts')
    fireEvent.click(shortsToggle)

    expect(handleChange).toHaveBeenCalledWith('include_shorts', true)
  })

  it('loads credentials for gdrive_ingest job type', async () => {
    const mockCredentials = {
      credentials: [
        { credential_id: 'cred1', credential_name: 'Test Account' },
      ],
    }

    fetch.mockResolvedValueOnce({
      json: () => Promise.resolve(mockCredentials),
    })

    render(
      <TaskParameters
        taskType="gdrive_ingest"
        taskTypes={mockTaskTypes}
      />
    )

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/credentials', { credentials: 'include' })
    })
  })

  it('shows message when no parameters are configured', () => {
    const emptyTaskType = {
      type: 'empty_job',
      name: 'Empty Job',
      required_params: [],
      optional_params: [],
    }

    render(
      <TaskParameters
        taskType="empty_job"
        taskTypes={[emptyTaskType]}
      />
    )

    expect(screen.getByText('This task type has no configurable parameters')).toBeInTheDocument()
  })

  it('renders object values as formatted JSON in read-only mode', () => {
    // Create a task type that includes metadata
    const metadataTaskType = {
      type: 'metadata_job',
      name: 'Metadata Job',
      required_params: ['channel_url'],
      optional_params: ['metadata'],
    }

    const values = {
      channel_url: 'https://youtube.com/@test',
      metadata: { project: 'test-project', department: 'engineering' },
    }

    render(
      <TaskParameters
        taskType="metadata_job"
        taskTypes={[...mockTaskTypes, metadataTaskType]}
        values={values}
        readOnly={true}
      />
    )

    // Check for the metadata label and the JSON content in the pre/code block
    expect(screen.getByText('Metadata')).toBeInTheDocument()
    const preElement = document.querySelector('pre')
    expect(preElement).toBeInTheDocument()
    expect(preElement.textContent).toContain('"project": "test-project"')
    expect(preElement.textContent).toContain('"department": "engineering"')
  })

  it('renders multi-select values in read-only mode', () => {
    const userTaskType = {
      type: 'user_job',
      name: 'User Job',
      required_params: ['user_types'],
      optional_params: [],
    }

    const values = {
      user_types: ['member', 'admin'],
    }

    render(
      <TaskParameters
        taskType="user_job"
        taskTypes={[userTaskType]}
        values={values}
        readOnly={true}
      />
    )

    expect(screen.getByText('Member, Admin')).toBeInTheDocument()
  })

  it('renders select values with labels in read-only mode', () => {
    const metricTaskType = {
      type: 'metric_job',
      name: 'Metric Job',
      required_params: ['aggregate_level'],
      optional_params: [],
    }

    const values = {
      aggregate_level: 'daily',
    }

    render(
      <TaskParameters
        taskType="metric_job"
        taskTypes={[metricTaskType]}
        values={values}
        readOnly={true}
      />
    )

    expect(screen.getByText('Daily')).toBeInTheDocument()
  })

  describe('Credential filtering by provider', () => {
    const hubspotTaskType = {
      type: 'hubspot_sync',
      name: 'HubSpot Sync',
      required_params: ['credential_id'],
      optional_params: ['limit'],
    }

    const websiteScrapeTaskType = {
      type: 'website_scrape',
      name: 'Website Scrape',
      required_params: ['start_url'],
      optional_params: ['max_pages'],
    }

    const allTaskTypes = [
      ...mockTaskTypes,
      hubspotTaskType,
      websiteScrapeTaskType,
    ]

    const mixedCredentials = {
      credentials: [
        { credential_id: 'google-cred-1', credential_name: 'Google Account', provider: 'google_drive' },
        { credential_id: 'hubspot-cred-1', credential_name: 'HubSpot Account', provider: 'hubspot' },
        { credential_id: 'google-cred-2', credential_name: 'Another Google', provider: 'google' },
      ],
    }

    it('filters for HubSpot credentials only when hubspot_sync is selected', async () => {
      fetch.mockResolvedValueOnce({
        json: () => Promise.resolve(mixedCredentials),
      })

      render(
        <TaskParameters
          taskType="hubspot_sync"
          taskTypes={allTaskTypes}
        />
      )

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/credentials', { credentials: 'include' })
      })

      // Should show HubSpot Authentication section
      await waitFor(() => {
        expect(screen.getByText('HubSpot Authentication')).toBeInTheDocument()
      })

      // Wait for dropdown to be populated with credentials
      await waitFor(() => {
        const select = screen.getByRole('combobox')
        const options = select.querySelectorAll('option')
        // Should have 2 options: "Choose a credential..." + 1 HubSpot credential
        expect(options.length).toBe(2)
        expect(options[1].textContent).toBe('HubSpot Account')
      })
    })

    it('filters for Google credentials only when gdrive_ingest is selected', async () => {
      fetch.mockResolvedValueOnce({
        json: () => Promise.resolve(mixedCredentials),
      })

      render(
        <TaskParameters
          taskType="gdrive_ingest"
          taskTypes={allTaskTypes}
        />
      )

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/credentials', { credentials: 'include' })
      })

      // Should show Google Drive Authentication section
      await waitFor(() => {
        expect(screen.getByText('Google Drive Authentication')).toBeInTheDocument()
      })

      // Wait for dropdown to be populated with credentials
      await waitFor(() => {
        const select = screen.getByRole('combobox')
        const options = select.querySelectorAll('option')
        // Should have 3 options: "Choose a credential..." + 2 Google credentials
        expect(options.length).toBe(3)
        expect(options[1].textContent).toBe('Google Account')
        expect(options[2].textContent).toBe('Another Google')
      })
    })

    it('does not show credential section for website_scrape', () => {
      render(
        <TaskParameters
          taskType="website_scrape"
          taskTypes={allTaskTypes}
        />
      )

      // Should NOT call fetch for credentials
      expect(fetch).not.toHaveBeenCalled()

      // Should not show any authentication section
      expect(screen.queryByText('Authentication')).not.toBeInTheDocument()
      expect(screen.queryByText('Google Drive Authentication')).not.toBeInTheDocument()
      expect(screen.queryByText('HubSpot Authentication')).not.toBeInTheDocument()
    })

    it('shows warning when no matching credentials exist for HubSpot', async () => {
      const googleOnlyCredentials = {
        credentials: [
          { credential_id: 'google-cred-1', credential_name: 'Google Account', provider: 'google_drive' },
        ],
      }

      fetch.mockResolvedValueOnce({
        json: () => Promise.resolve(googleOnlyCredentials),
      })

      render(
        <TaskParameters
          taskType="hubspot_sync"
          taskTypes={allTaskTypes}
        />
      )

      await waitFor(() => {
        expect(screen.getByText(/No HubSpot credentials found/)).toBeInTheDocument()
      })
    })

    it('shows warning when no matching credentials exist for Google Drive', async () => {
      const hubspotOnlyCredentials = {
        credentials: [
          { credential_id: 'hubspot-cred-1', credential_name: 'HubSpot Account', provider: 'hubspot' },
        ],
      }

      fetch.mockResolvedValueOnce({
        json: () => Promise.resolve(hubspotOnlyCredentials),
      })

      render(
        <TaskParameters
          taskType="gdrive_ingest"
          taskTypes={allTaskTypes}
        />
      )

      await waitFor(() => {
        expect(screen.getByText(/No Google credentials found/)).toBeInTheDocument()
      })
    })

    it('auto-selects credential when only one matching credential exists', async () => {
      const singleHubspotCred = {
        credentials: [
          { credential_id: 'hubspot-only', credential_name: 'Only HubSpot', provider: 'hubspot' },
          { credential_id: 'google-cred', credential_name: 'Google Cred', provider: 'google_drive' },
        ],
      }

      const handleChange = vi.fn()

      fetch.mockResolvedValueOnce({
        json: () => Promise.resolve(singleHubspotCred),
      })

      render(
        <TaskParameters
          taskType="hubspot_sync"
          taskTypes={allTaskTypes}
          onChange={handleChange}
        />
      )

      await waitFor(() => {
        // Should auto-select the only HubSpot credential
        expect(handleChange).toHaveBeenCalledWith('credential_id', 'hubspot-only')
      })
    })

    it('renders limit parameter for hubspot_sync', () => {
      fetch.mockResolvedValueOnce({
        json: () => Promise.resolve({ credentials: [] }),
      })

      render(
        <TaskParameters
          taskType="hubspot_sync"
          taskTypes={allTaskTypes}
        />
      )

      expect(screen.getByText('Max Deals')).toBeInTheDocument()
    })
  })
})
