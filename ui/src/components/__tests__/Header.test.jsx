import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  Header,
  dotConnected, dotDisconnected,
  sessionPillStyles, sessionConnectorStyles,
  startBtnEnabled, startBtnDisabled,
} from '../Header'

const SESSION_STAGE_KEYS = ['triage', 'plan', 'implement', 'review', 'merged']
const STAGE_COLORS = {
  triage: 'var(--triage-green)',
  plan: 'var(--purple)',
  implement: 'var(--accent)',
  review: 'var(--orange)',
  merged: 'var(--green)',
}

describe('Header pre-computed styles', () => {
  describe('dot variants', () => {
    it('dotConnected has green background', () => {
      expect(dotConnected).toMatchObject({
        width: 8, height: 8, borderRadius: '50%',
        background: 'var(--green)',
      })
    })

    it('dotDisconnected has red background', () => {
      expect(dotDisconnected).toMatchObject({
        width: 8, height: 8, borderRadius: '50%',
        background: 'var(--red)',
      })
    })
  })

  describe('session pill styles', () => {
    it('has entries for all 5 session stages including merged', () => {
      for (const key of SESSION_STAGE_KEYS) {
        expect(sessionPillStyles).toHaveProperty(key)
      }
    })

    it('uses correct color with opacity suffix for each stage', () => {
      for (const key of SESSION_STAGE_KEYS) {
        expect(sessionPillStyles[key].background).toBe(STAGE_COLORS[key] + '20')
        expect(sessionPillStyles[key].color).toBe(STAGE_COLORS[key])
        expect(sessionPillStyles[key].borderColor).toBe(STAGE_COLORS[key] + '44')
      }
    })

    it('session pill styles include base sessionPill properties', () => {
      for (const key of SESSION_STAGE_KEYS) {
        expect(sessionPillStyles[key]).toMatchObject({
          padding: '3px 10px',
          borderRadius: 10,
          fontSize: 12,
          fontWeight: 600,
        })
      }
    })
  })

  describe('session connector styles', () => {
    it('has entries for all 5 session stages', () => {
      for (const key of SESSION_STAGE_KEYS) {
        expect(sessionConnectorStyles).toHaveProperty(key)
      }
    })

    it('uses stage color with opacity suffix for background', () => {
      for (const key of SESSION_STAGE_KEYS) {
        expect(sessionConnectorStyles[key].background).toBe(STAGE_COLORS[key] + '55')
      }
    })

    it('connector has compact dimensions (thinner than process connectors)', () => {
      for (const key of SESSION_STAGE_KEYS) {
        expect(sessionConnectorStyles[key]).toMatchObject({ width: 12, height: 1, flexShrink: 0 })
      }
    })

  })

  describe('start button variants', () => {
    it('startBtnEnabled has opacity 1 and pointer cursor', () => {
      expect(startBtnEnabled).toMatchObject({ opacity: 1, cursor: 'pointer' })
      expect(startBtnEnabled.background).toBe('var(--btn-green)')
    })

    it('startBtnDisabled has opacity 0.4 and not-allowed cursor', () => {
      expect(startBtnDisabled).toMatchObject({ opacity: 0.4, cursor: 'not-allowed' })
    })
  })

  it('style objects are referentially stable', () => {
    expect(dotConnected).toBe(dotConnected)
    expect(startBtnEnabled).toBe(startBtnEnabled)
    expect(sessionPillStyles.triage).toBe(sessionPillStyles.triage)
  })
})

describe('Header component', () => {
  const defaultProps = {
    sessionCounts: { triage: 0, plan: 0, implement: 0, review: 0, merged: 0 },
    connected: true,
    orchestratorStatus: 'idle',
    onStart: () => {},
    onStop: () => {},
    phase: 'idle',
    workers: {},
  }

  it('renders without errors', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByText('HYDRA')).toBeInTheDocument()
  })

  it('renders Start button when idle', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByText('Start')).toBeInTheDocument()
  })

  it('renders Stop button when running', () => {
    render(<Header {...defaultProps} orchestratorStatus="running" />)
    expect(screen.getByText('Stop')).toBeInTheDocument()
  })

  it('renders session pills with all 5 stage labels', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByText('TRIAGE')).toBeInTheDocument()
    expect(screen.getByText('PLAN')).toBeInTheDocument()
    expect(screen.getByText('IMPLEMENT')).toBeInTheDocument()
    expect(screen.getByText('REVIEW')).toBeInTheDocument()
    expect(screen.getByText('MERGED')).toBeInTheDocument()
  })

  it('renders session pill counts correctly', () => {
    const counts = { triage: 3, plan: 5, implement: 4, review: 2, merged: 7 }
    render(<Header {...defaultProps} sessionCounts={counts} />)
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
  })

  it('renders session pill counts as 0 when all zero', () => {
    render(<Header {...defaultProps} />)
    // All 5 session pills show 0
    const zeros = screen.getAllByText('0')
    expect(zeros.length).toBe(5)
  })

  it('renders workload summary with empty workers', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByText('0 total')).toBeInTheDocument()
    expect(screen.getByText('0 active')).toBeInTheDocument()
    expect(screen.getByText('0 done')).toBeInTheDocument()
    expect(screen.getByText('0 failed')).toBeInTheDocument()
  })

  it('renders workload summary with workers in various statuses', () => {
    const workers = {
      1: { status: 'running', worker: 1, role: 'implementer', title: 'Issue #1', branch: '', transcript: [], pr: null },
      2: { status: 'running', worker: 2, role: 'implementer', title: 'Issue #2', branch: '', transcript: [], pr: null },
      3: { status: 'done', worker: 3, role: 'implementer', title: 'Issue #3', branch: '', transcript: [], pr: null },
      4: { status: 'done', worker: 4, role: 'planner', title: 'Plan #4', branch: '', transcript: [], pr: null },
      5: { status: 'failed', worker: 5, role: 'implementer', title: 'Issue #5', branch: '', transcript: [], pr: null },
    }
    render(<Header {...defaultProps} workers={workers} />)
    expect(screen.getByText('5 total')).toBeInTheDocument()
    expect(screen.getByText('2 active')).toBeInTheDocument()
    expect(screen.getByText('2 done')).toBeInTheDocument()
    expect(screen.getByText('1 failed')).toBeInTheDocument()
  })

  it('counts quality_fix workers as active in workload summary', () => {
    const workers = {
      1: { status: 'quality_fix', worker: 1, role: 'implementer', title: 'Fix #1', branch: '', transcript: [], pr: null },
      2: { status: 'queued', worker: 2, role: 'implementer', title: 'Issue #2', branch: '', transcript: [], pr: null },
    }
    render(<Header {...defaultProps} workers={workers} />)
    expect(screen.getByText('2 total')).toBeInTheDocument()
    expect(screen.getByText('1 active')).toBeInTheDocument()
  })

  it('renders connector lines between session pills instead of arrows', () => {
    render(<Header {...defaultProps} />)
    // No arrow characters should be rendered
    expect(screen.queryByText('\u2192')).toBeNull()
    // 5 session stages means 4 connectors rendered as divs with testid
    const connectors = screen.getAllByTestId('session-connector')
    expect(connectors.length).toBe(4)
  })

  it('renders Session label', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByText('Session')).toBeInTheDocument()
  })

  it('renders tagline as two stacked lines', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByText('Intent in.')).toBeInTheDocument()
    expect(screen.getByText('Software out.')).toBeInTheDocument()
  })

  it('controls section has marginLeft for spacing from pills', () => {
    render(<Header {...defaultProps} />)
    const startBtn = screen.getByText('Start')
    const controlsDiv = startBtn.parentElement
    expect(controlsDiv.style.marginLeft).toBe('10px')
  })

  it('left section has flexShrink 0 to prevent collapsing', () => {
    render(<Header {...defaultProps} />)
    const logo = screen.getByText('HYDRA')
    // logo is inside logoGroup -> left div; go up two levels past logoGroup
    const leftDiv = logo.parentElement.parentElement
    expect(leftDiv.style.flexShrink).toBe('0')
  })

  it('controls section has flexShrink 0 to prevent collapsing', () => {
    render(<Header {...defaultProps} />)
    const startBtn = screen.getByText('Start')
    const controlsDiv = startBtn.parentElement
    expect(controlsDiv.style.flexShrink).toBe('0')
  })

  it('center section has minWidth 0 and overflow hidden for graceful truncation', () => {
    render(<Header {...defaultProps} />)
    const sessionLabel = screen.getByText('Session')
    const centerDiv = sessionLabel.closest('div').parentElement
    expect(centerDiv.style.minWidth).toBe('0px')
    expect(centerDiv.style.overflow).toBe('hidden')
  })

  describe('stopping state with active workers', () => {
    const activeWorkers = {
      1: { status: 'running', worker: 1, role: 'implementer', title: 'Issue #1', branch: '', transcript: [], pr: null },
      2: { status: 'done', worker: 2, role: 'implementer', title: 'Issue #2', branch: '', transcript: [], pr: null },
    }
    const allDoneWorkers = {
      1: { status: 'done', worker: 1, role: 'implementer', title: 'Issue #1', branch: '', transcript: [], pr: null },
      2: { status: 'done', worker: 2, role: 'implementer', title: 'Issue #2', branch: '', transcript: [], pr: null },
    }
    const planningWorkers = {
      1: { status: 'planning', worker: 1, role: 'planner', title: 'Plan #1', branch: '', transcript: [], pr: null },
    }

    it('shows Start when orchestratorStatus is idle even with stale active workers', () => {
      render(<Header {...defaultProps} orchestratorStatus="idle" workers={activeWorkers} />)
      expect(screen.getByText('Start')).toBeInTheDocument()
      expect(screen.queryByText('Stopping\u2026')).toBeNull()
    })

    it('shows Start when idle and all workers are done', () => {
      render(<Header {...defaultProps} orchestratorStatus="idle" workers={allDoneWorkers} />)
      expect(screen.getByText('Start')).toBeInTheDocument()
      expect(screen.queryByText('Stopping\u2026')).toBeNull()
    })

    it('shows Stopping badge when orchestratorStatus is stopping', () => {
      render(<Header {...defaultProps} orchestratorStatus="stopping" workers={{}} />)
      expect(screen.getByText('Stopping\u2026')).toBeInTheDocument()
      expect(screen.queryByText('Start')).toBeNull()
      expect(screen.queryByText('Stop')).toBeNull()
    })

    it('shows Start when orchestratorStatus is idle even with stale planning workers', () => {
      render(<Header {...defaultProps} orchestratorStatus="idle" workers={planningWorkers} />)
      expect(screen.getByText('Start')).toBeInTheDocument()
      expect(screen.queryByText('Stopping\u2026')).toBeNull()
    })

    it('shows Start when orchestratorStatus is done and no active workers', () => {
      render(<Header {...defaultProps} orchestratorStatus="done" workers={allDoneWorkers} />)
      expect(screen.getByText('Start')).toBeInTheDocument()
    })

    it('shows Start when orchestratorStatus is done even with stale active workers', () => {
      render(<Header {...defaultProps} orchestratorStatus="done" workers={activeWorkers} />)
      expect(screen.getByText('Start')).toBeInTheDocument()
      expect(screen.queryByText('Stopping\u2026')).toBeNull()
    })
  })

  describe('minimum stopping hold timer', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })
    afterEach(() => {
      vi.useRealTimers()
    })

    it('clears Stopping immediately when transitioning to idle with no active workers', () => {
      const { rerender } = render(
        <Header {...defaultProps} orchestratorStatus="stopping" workers={{}} />
      )
      expect(screen.getByText('Stopping\u2026')).toBeInTheDocument()

      // Transition to idle with no active workers — second effect clears held state early
      rerender(<Header {...defaultProps} orchestratorStatus="idle" workers={{}} />)

      expect(screen.getByText('Start')).toBeInTheDocument()
    })

    it('holds Stopping badge while workers are still active after idle', () => {
      const activeWorkers = {
        1: { status: 'running', worker: 1, role: 'implementer', title: 'Issue #1', branch: '', transcript: [], pr: null },
      }

      const { rerender } = render(
        <Header {...defaultProps} orchestratorStatus="stopping" workers={activeWorkers} />
      )
      expect(screen.getByText('Stopping\u2026')).toBeInTheDocument()

      // Status transitions to idle but workers still active
      rerender(<Header {...defaultProps} orchestratorStatus="idle" workers={activeWorkers} />)

      // Should still show Stopping because workers are active
      expect(screen.getByText('Stopping\u2026')).toBeInTheDocument()
      expect(screen.queryByText('Start')).toBeNull()

      // Workers finish
      rerender(<Header {...defaultProps} orchestratorStatus="idle" workers={{}} />)

      // Now Start should appear
      expect(screen.getByText('Start')).toBeInTheDocument()
    })

    it('handles disconnect during stopping gracefully', () => {
      render(
        <Header {...defaultProps} orchestratorStatus="stopping" connected={false} workers={{}} />
      )
      expect(screen.getByText('Stopping\u2026')).toBeInTheDocument()
      expect(screen.queryByText('Start')).toBeNull()
    })
  })
})
