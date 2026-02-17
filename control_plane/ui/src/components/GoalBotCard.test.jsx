/**
 * Tests for GoalBotCard component
 */

import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import GoalBotCard from './GoalBotCard'

describe('GoalBotCard', () => {
  const mockBot = {
    bot_id: 'bot-123',
    name: 'test_bot',
    description: 'A test goal bot',
    is_enabled: true,
    is_paused: false,
    has_running_job: false,
    schedule_type: 'interval',
    schedule_config: { interval_seconds: 86400 },
    next_run_at: null,
    last_run_at: null,
  }

  const mockOnClick = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
  })

  describe('rendering', () => {
    it('should render bot name and description', () => {
      render(<GoalBotCard bot={mockBot} onClick={mockOnClick} />)

      expect(screen.getByText('test_bot')).toBeInTheDocument()
      expect(screen.getByText('A test goal bot')).toBeInTheDocument()
    })

    it('should show Active badge when enabled', () => {
      render(<GoalBotCard bot={mockBot} onClick={mockOnClick} />)

      expect(screen.getByText('Active')).toBeInTheDocument()
    })

    it('should show Disabled badge when not enabled', () => {
      const disabledBot = { ...mockBot, is_enabled: false }
      render(<GoalBotCard bot={disabledBot} onClick={mockOnClick} />)

      expect(screen.getByText('Disabled')).toBeInTheDocument()
    })

    it('should show Running badge when has running job', () => {
      const runningBot = { ...mockBot, has_running_job: true }
      render(<GoalBotCard bot={runningBot} onClick={mockOnClick} />)

      expect(screen.getByText('Running')).toBeInTheDocument()
    })
  })

  describe('schedule formatting', () => {
    it('should format daily interval correctly', () => {
      render(<GoalBotCard bot={mockBot} onClick={mockOnClick} />)

      expect(screen.getByText('Every 1 day')).toBeInTheDocument()
    })

    it('should format multi-day interval correctly', () => {
      const multiDayBot = {
        ...mockBot,
        schedule_config: { interval_seconds: 172800 }, // 2 days
      }
      render(<GoalBotCard bot={multiDayBot} onClick={mockOnClick} />)

      expect(screen.getByText('Every 2 days')).toBeInTheDocument()
    })

    it('should format hourly interval correctly', () => {
      const hourlyBot = {
        ...mockBot,
        schedule_config: { interval_seconds: 3600 },
      }
      render(<GoalBotCard bot={hourlyBot} onClick={mockOnClick} />)

      expect(screen.getByText('Every 1 hour')).toBeInTheDocument()
    })

    it('should format minute interval correctly', () => {
      const minuteBot = {
        ...mockBot,
        schedule_config: { interval_seconds: 1800 }, // 30 minutes
      }
      render(<GoalBotCard bot={minuteBot} onClick={mockOnClick} />)

      expect(screen.getByText('Every 30 mins')).toBeInTheDocument()
    })

    it('should format cron schedule correctly', () => {
      const cronBot = {
        ...mockBot,
        schedule_type: 'cron',
        schedule_config: { cron_expression: '0 9 * * *' },
      }
      render(<GoalBotCard bot={cronBot} onClick={mockOnClick} />)

      expect(screen.getByText('0 9 * * *')).toBeInTheDocument()
    })
  })

  describe('next run formatting', () => {
    it('should show "Due now" when next_run_at is in the past', () => {
      const pastDueBot = {
        ...mockBot,
        next_run_at: new Date(Date.now() - 1000).toISOString(),
      }
      render(<GoalBotCard bot={pastDueBot} onClick={mockOnClick} />)

      expect(screen.getByText('Due now')).toBeInTheDocument()
    })

    it('should show minutes when due soon', () => {
      const soonBot = {
        ...mockBot,
        next_run_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(), // 30 minutes
      }
      render(<GoalBotCard bot={soonBot} onClick={mockOnClick} />)

      expect(screen.getByText(/Due in \d+m/)).toBeInTheDocument()
    })

    it('should not show next run when disabled', () => {
      const disabledBot = {
        ...mockBot,
        is_enabled: false,
        next_run_at: new Date(Date.now() + 3600000).toISOString(),
      }
      render(<GoalBotCard bot={disabledBot} onClick={mockOnClick} />)

      expect(screen.queryByText(/Due in/)).not.toBeInTheDocument()
    })
  })

  describe('interactions', () => {
    it('should call onClick when card is clicked', () => {
      render(<GoalBotCard bot={mockBot} onClick={mockOnClick} />)

      const card = screen.getByText('test_bot').closest('.agent-card')
      fireEvent.click(card)

      expect(mockOnClick).toHaveBeenCalledWith(mockBot)
    })
  })
})
