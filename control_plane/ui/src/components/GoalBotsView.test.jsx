/**
 * Tests for GoalBotsView component
 */

import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import GoalBotsView from './GoalBotsView'

describe('GoalBotsView', () => {
  const mockGoalBots = [
    {
      bot_id: 'bot-1',
      name: 'test_bot_1',
      description: 'First test bot',
      is_enabled: true,
      is_paused: false,
      has_running_job: false,
      schedule_type: 'interval',
      schedule_config: { interval_seconds: 86400 },
      next_run_at: null,
    },
    {
      bot_id: 'bot-2',
      name: 'test_bot_2',
      description: 'Second test bot',
      is_enabled: false,
      is_paused: false,
      has_running_job: false,
      schedule_type: 'cron',
      schedule_config: { cron_expression: '0 9 * * *' },
      next_run_at: null,
    },
  ]

  const mockCallbacks = {
    onRefresh: jest.fn(),
    onFetchDetails: jest.fn(),
    onToggle: jest.fn(),
    onTrigger: jest.fn(),
    onCancel: jest.fn(),
    onFetchRuns: jest.fn().mockResolvedValue({ runs: [] }),
    onFetchRunDetails: jest.fn().mockResolvedValue({}),
    onResetState: jest.fn(),
    setSelectedBot: jest.fn(),
  }

  beforeEach(() => {
    jest.clearAllMocks()
  })

  describe('loading state', () => {
    it('should show loading message when loading', () => {
      render(
        <GoalBotsView
          goalBots={[]}
          loading={true}
          error={null}
          selectedBot={null}
          selectedBotDetails={null}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('Loading goals...')).toBeInTheDocument()
    })
  })

  describe('error state', () => {
    it('should show error message when error occurs', () => {
      render(
        <GoalBotsView
          goalBots={[]}
          loading={false}
          error="Network error"
          selectedBot={null}
          selectedBotDetails={null}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('Error: Network error')).toBeInTheDocument()
    })

    it('should show retry button on error', () => {
      render(
        <GoalBotsView
          goalBots={[]}
          loading={false}
          error="Network error"
          selectedBot={null}
          selectedBotDetails={null}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('Retry')).toBeInTheDocument()
    })

    it('should call onRefresh when retry clicked', () => {
      render(
        <GoalBotsView
          goalBots={[]}
          loading={false}
          error="Network error"
          selectedBot={null}
          selectedBotDetails={null}
          {...mockCallbacks}
        />
      )

      fireEvent.click(screen.getByText('Retry'))
      expect(mockCallbacks.onRefresh).toHaveBeenCalled()
    })
  })

  describe('empty state', () => {
    it('should show empty state when no goal bots', () => {
      render(
        <GoalBotsView
          goalBots={[]}
          loading={false}
          error={null}
          selectedBot={null}
          selectedBotDetails={null}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('No Goals')).toBeInTheDocument()
      expect(screen.getByText(/Goals are registered automatically/)).toBeInTheDocument()
    })
  })

  describe('goal bots list', () => {
    it('should display goal bots count in header', () => {
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={null}
          selectedBotDetails={null}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('Goals (2)')).toBeInTheDocument()
    })

    it('should render all goal bot cards', () => {
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={null}
          selectedBotDetails={null}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('test_bot_1')).toBeInTheDocument()
      expect(screen.getByText('test_bot_2')).toBeInTheDocument()
    })

    it('should show refresh button', () => {
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={null}
          selectedBotDetails={null}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('Refresh')).toBeInTheDocument()
    })

    it('should call onRefresh when refresh button clicked', () => {
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={null}
          selectedBotDetails={null}
          {...mockCallbacks}
        />
      )

      fireEvent.click(screen.getByText('Refresh'))
      expect(mockCallbacks.onRefresh).toHaveBeenCalled()
    })
  })

  describe('modal interactions', () => {
    const mockBotDetails = {
      bot_id: 'bot-1',
      name: 'test_bot_1',
      description: 'First test bot',
      agent_name: 'research_agent',
      schedule_type: 'interval',
      schedule_config: { interval_seconds: 86400 },
      max_runtime_seconds: 3600,
      max_iterations: 10,
      tools: ['search', 'browse'],
      recent_runs: [],
      state: null,
    }

    it('should show modal when bot is selected', () => {
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={mockGoalBots[0]}
          selectedBotDetails={mockBotDetails}
          {...mockCallbacks}
        />
      )

      // Modal should be visible with tabs
      expect(screen.getByText('Details')).toBeInTheDocument()
      expect(screen.getByText('Run History')).toBeInTheDocument()
      expect(screen.getByText('State')).toBeInTheDocument()
      // Modal title contains the bot name
      expect(screen.getByRole('heading', { level: 2, name: /test_bot_1/ })).toBeInTheDocument()
    })

    it('should show Run Now button when bot is not running', () => {
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={mockGoalBots[0]}
          selectedBotDetails={mockBotDetails}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('Run Now')).toBeInTheDocument()
    })

    it('should show Cancel Run button when bot is running', () => {
      const runningBot = { ...mockGoalBots[0], has_running_job: true }
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={runningBot}
          selectedBotDetails={mockBotDetails}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('Cancel Run')).toBeInTheDocument()
    })

    it('should show Disable button when bot is enabled', () => {
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={mockGoalBots[0]}
          selectedBotDetails={mockBotDetails}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('Disable')).toBeInTheDocument()
    })

    it('should show Enable button when bot is disabled', () => {
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={mockGoalBots[1]}
          selectedBotDetails={mockBotDetails}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('Enable')).toBeInTheDocument()
    })

    it('should call onTrigger when Run Now clicked', () => {
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={mockGoalBots[0]}
          selectedBotDetails={mockBotDetails}
          {...mockCallbacks}
        />
      )

      fireEvent.click(screen.getByText('Run Now'))
      expect(mockCallbacks.onTrigger).toHaveBeenCalledWith('bot-1')
    })

    it('should call onCancel when Cancel Run clicked', () => {
      const runningBot = { ...mockGoalBots[0], has_running_job: true }
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={runningBot}
          selectedBotDetails={mockBotDetails}
          {...mockCallbacks}
        />
      )

      fireEvent.click(screen.getByText('Cancel Run'))
      expect(mockCallbacks.onCancel).toHaveBeenCalledWith('bot-1')
    })

    it('should call onToggle when Disable/Enable clicked', () => {
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={mockGoalBots[0]}
          selectedBotDetails={mockBotDetails}
          {...mockCallbacks}
        />
      )

      fireEvent.click(screen.getByText('Disable'))
      expect(mockCallbacks.onToggle).toHaveBeenCalledWith('bot-1')
    })

    it('should display bot details in Details tab', () => {
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={mockGoalBots[0]}
          selectedBotDetails={mockBotDetails}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('Configuration')).toBeInTheDocument()
      expect(screen.getByText('research_agent')).toBeInTheDocument()
    })

    it('should display tools when present', () => {
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={mockGoalBots[0]}
          selectedBotDetails={mockBotDetails}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('Tools')).toBeInTheDocument()
      expect(screen.getByText('search')).toBeInTheDocument()
      expect(screen.getByText('browse')).toBeInTheDocument()
    })

    it('should display run statistics section', () => {
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={mockGoalBots[0]}
          selectedBotDetails={mockBotDetails}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('Run Statistics')).toBeInTheDocument()
      expect(screen.getByText('Total Runs')).toBeInTheDocument()
      expect(screen.getByText('Last Run')).toBeInTheDocument()
    })

    it('should show "Never" for last run when no runs exist', () => {
      const detailsNoRuns = { ...mockBotDetails, recent_runs: [], total_runs: 0 }
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={mockGoalBots[0]}
          selectedBotDetails={detailsNoRuns}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('Never')).toBeInTheDocument()
      expect(screen.getByText('0')).toBeInTheDocument()
    })

    it('should show last run details when runs exist', () => {
      const detailsWithRuns = {
        ...mockBotDetails,
        total_runs: 5,
        recent_runs: [
          {
            run_id: 'run-1',
            status: 'completed',
            started_at: '2026-02-16T10:00:00Z',
            duration_seconds: 120,
          }
        ]
      }
      render(
        <GoalBotsView
          goalBots={mockGoalBots}
          loading={false}
          error={null}
          selectedBot={mockGoalBots[0]}
          selectedBotDetails={detailsWithRuns}
          {...mockCallbacks}
        />
      )

      expect(screen.getByText('5')).toBeInTheDocument()
      expect(screen.getByText('Last Status')).toBeInTheDocument()
      expect(screen.getByText('completed')).toBeInTheDocument()
      expect(screen.getByText('Last Duration')).toBeInTheDocument()
      expect(screen.getByText('2m')).toBeInTheDocument()
    })
  })
})
