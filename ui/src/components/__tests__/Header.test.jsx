import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { deriveStageStatus } from '../../hooks/useStageStatus'
import {
  dotConnected, dotDisconnected,
  startBtnEnabled, startBtnDisabled,
  panelToggleStyle, panelToggleActiveStyle,
} from '../Header'

const mockUseHydra = vi.fn()

vi.mock('../../context/HydraContext', () => ({
  useHydra: (...args) => mockUseHydra(...args),
}))

const { Header } = await import('../Header')

function mockStageStatus(workers = {}) {
  return deriveStageStatus({}, workers, [], {})
}

beforeEach(() => {
  mockUseHydra.mockReturnValue({ stageStatus: mockStageStatus() })
})

describe('Header pre-computed panel toggle styles', () => {
  it('panelToggleStyle has muted border and text-muted color', () => {
    expect(panelToggleStyle).toMatchObject({
      fontSize: 11,
      fontWeight: 600,
      cursor: 'pointer',
      color: 'var(--text-muted)',
    })
  })

  it('panelToggleActiveStyle has accent border, accentSubtle background, and accent color', () => {
    expect(panelToggleActiveStyle).toMatchObject({
      fontSize: 11,
      fontWeight: 600,
      cursor: 'pointer',
      color: 'var(--accent)',
      background: 'var(--accent-subtle)',
      border: '1px solid var(--accent)',
    })
  })

  it('style objects are referentially stable', () => {
    expect(panelToggleStyle).toBe(panelToggleStyle)
    expect(panelToggleActiveStyle).toBe(panelToggleActiveStyle)
  })
})

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
  })
})

describe('Header component', () => {
  const defaultProps = {
    connected: true,
    orchestratorStatus: 'idle',
    onStart: () => {},
    onStop: () => {},
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
    mockUseHydra.mockReturnValue({ stageStatus: mockStageStatus(workers) })
    render(<Header {...defaultProps} />)
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
    mockUseHydra.mockReturnValue({ stageStatus: mockStageStatus(workers) })
    render(<Header {...defaultProps} />)
    expect(screen.getByText('2 total')).toBeInTheDocument()
    expect(screen.getByText('1 active')).toBeInTheDocument()
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

  it('controls section has marginLeft for spacing from center content', () => {
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
      mockUseHydra.mockReturnValue({ stageStatus: mockStageStatus(activeWorkers) })
      render(<Header {...defaultProps} orchestratorStatus="idle" />)
      expect(screen.getByText('Start')).toBeInTheDocument()
      expect(screen.queryByText('Stopping\u2026')).toBeNull()
    })

    it('shows Start when idle and all workers are done', () => {
      mockUseHydra.mockReturnValue({ stageStatus: mockStageStatus(allDoneWorkers) })
      render(<Header {...defaultProps} orchestratorStatus="idle" />)
      expect(screen.getByText('Start')).toBeInTheDocument()
      expect(screen.queryByText('Stopping\u2026')).toBeNull()
    })

    it('shows Stopping badge when orchestratorStatus is stopping', () => {
      render(<Header {...defaultProps} orchestratorStatus="stopping" />)
      expect(screen.getByText('Stopping\u2026')).toBeInTheDocument()
      expect(screen.queryByText('Start')).toBeNull()
      expect(screen.queryByText('Stop')).toBeNull()
    })

    it('shows Start when orchestratorStatus is idle even with stale planning workers', () => {
      mockUseHydra.mockReturnValue({ stageStatus: mockStageStatus(planningWorkers) })
      render(<Header {...defaultProps} orchestratorStatus="idle" />)
      expect(screen.getByText('Start')).toBeInTheDocument()
      expect(screen.queryByText('Stopping\u2026')).toBeNull()
    })

    it('shows Start when orchestratorStatus is done and no active workers', () => {
      mockUseHydra.mockReturnValue({ stageStatus: mockStageStatus(allDoneWorkers) })
      render(<Header {...defaultProps} orchestratorStatus="done" />)
      expect(screen.getByText('Start')).toBeInTheDocument()
    })

    it('shows Start when orchestratorStatus is done even with stale active workers', () => {
      mockUseHydra.mockReturnValue({ stageStatus: mockStageStatus(activeWorkers) })
      render(<Header {...defaultProps} orchestratorStatus="done" />)
      expect(screen.getByText('Start')).toBeInTheDocument()
      expect(screen.queryByText('Stopping\u2026')).toBeNull()
    })

    it('shows Credits Paused badge and Stop button when credits_paused', () => {
      render(<Header {...defaultProps} orchestratorStatus="credits_paused" />)
      expect(screen.getByText('Credits Paused')).toBeInTheDocument()
      expect(screen.getByText('Stop')).toBeInTheDocument()
      expect(screen.queryByText('Start')).toBeNull()
    })
  })

  describe('pipeline panel toggle button', () => {
    it('does not render toggle button when onTogglePipelinePanel is not provided', () => {
      render(<Header {...defaultProps} />)
      expect(screen.queryByTestId('pipeline-panel-toggle')).not.toBeInTheDocument()
    })

    it('renders Pipeline toggle button when onTogglePipelinePanel is provided', () => {
      render(<Header {...defaultProps} onTogglePipelinePanel={() => {}} pipelinePanelOpen={true} />)
      expect(screen.getByTestId('pipeline-panel-toggle')).toBeInTheDocument()
      expect(screen.getByTestId('pipeline-panel-toggle')).toHaveTextContent('Pipeline')
    })

    it('calls onTogglePipelinePanel when button is clicked', () => {
      const onToggle = vi.fn()
      render(<Header {...defaultProps} onTogglePipelinePanel={onToggle} pipelinePanelOpen={true} />)
      fireEvent.click(screen.getByTestId('pipeline-panel-toggle'))
      expect(onToggle).toHaveBeenCalledTimes(1)
    })

    it('uses active style when pipelinePanelOpen is true', () => {
      render(<Header {...defaultProps} onTogglePipelinePanel={() => {}} pipelinePanelOpen={true} />)
      const btn = screen.getByTestId('pipeline-panel-toggle')
      expect(btn.style.color).toBe('var(--accent)')
      expect(btn.style.background).toBe('var(--accent-subtle)')
    })

    it('uses inactive style when pipelinePanelOpen is false', () => {
      render(<Header {...defaultProps} onTogglePipelinePanel={() => {}} pipelinePanelOpen={false} />)
      const btn = screen.getByTestId('pipeline-panel-toggle')
      expect(btn.style.color).toBe('var(--text-muted)')
      expect(btn.style.background).toBe('var(--surface)')
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
        <Header {...defaultProps} orchestratorStatus="stopping" />
      )
      expect(screen.getByText('Stopping\u2026')).toBeInTheDocument()

      // Transition to idle with no active workers — second effect clears held state early
      rerender(<Header {...defaultProps} orchestratorStatus="idle" />)

      expect(screen.getByText('Start')).toBeInTheDocument()
    })

    it('holds Stopping badge while workers are still active after idle', () => {
      const activeWorkers = {
        1: { status: 'running', worker: 1, role: 'implementer', title: 'Issue #1', branch: '', transcript: [], pr: null },
      }

      mockUseHydra.mockReturnValue({ stageStatus: mockStageStatus(activeWorkers) })
      const { rerender } = render(
        <Header {...defaultProps} orchestratorStatus="stopping" />
      )
      expect(screen.getByText('Stopping\u2026')).toBeInTheDocument()

      // Status transitions to idle but workers still active
      rerender(<Header {...defaultProps} orchestratorStatus="idle" />)

      // Should still show Stopping because workers are active
      expect(screen.getByText('Stopping\u2026')).toBeInTheDocument()
      expect(screen.queryByText('Start')).toBeNull()

      // Workers finish
      mockUseHydra.mockReturnValue({ stageStatus: mockStageStatus({}) })
      rerender(<Header {...defaultProps} orchestratorStatus="idle" />)

      // Now Start should appear
      expect(screen.getByText('Start')).toBeInTheDocument()
    })

    it('handles disconnect during stopping gracefully', () => {
      render(
        <Header {...defaultProps} orchestratorStatus="stopping" connected={false} />
      )
      expect(screen.getByText('Stopping\u2026')).toBeInTheDocument()
      expect(screen.queryByText('Start')).toBeNull()
    })
  })
})
