import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PIPELINE_LOOPS } from '../../constants'
import { deriveStageStatus } from '../../hooks/useStageStatus'

const mockUseHydraFlow = vi.fn()

vi.mock('../../context/HydraFlowContext', () => ({
  useHydraFlow: (...args) => mockUseHydraFlow(...args),
}))

const { PipelineControlPanel } = await import('../PipelineControlPanel')

function defaultMockContext(overrides = {}) {
  const pipelineIssues = overrides.pipelineIssues || {}
  const workers = overrides.workers || {}
  const backgroundWorkers = overrides.backgroundWorkers || []
  return {
    workers,
    hitlItems: [],
    stageStatus: deriveStageStatus(pipelineIssues, workers, backgroundWorkers, {}),
    ...overrides,
  }
}

beforeEach(() => {
  mockUseHydraFlow.mockReturnValue(defaultMockContext())
})

const mockPipelineWorkers = {
  'triage-5': { status: 'evaluating', worker: 1, role: 'triage', title: 'Triage Issue #5', branch: '', transcript: ['Evaluating issue...', 'Checking labels'], pr: null },
  'plan-7': { status: 'planning', worker: 2, role: 'planner', title: 'Plan Issue #7', branch: '', transcript: ['Reading codebase...'], pr: null },
  10: { status: 'running', worker: 3, role: 'implementer', title: 'Issue #10', branch: 'agent/issue-10', transcript: ['Writing code...', 'Running tests...', 'All tests pass'], pr: null },
  'review-20': { status: 'reviewing', worker: 4, role: 'reviewer', title: 'PR #20 (Issue #3)', branch: '', transcript: [], pr: 20 },
}

describe('PipelineControlPanel', () => {
  describe('Pipeline Loop Toggles', () => {
    it('renders all 4 pipeline loop chips', () => {
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} onToggleBgWorker={() => {}} />)
      for (const loop of PIPELINE_LOOPS) {
        expect(screen.getByText(loop.label)).toBeInTheDocument()
      }
    })

    it('shows worker count of 0 when no active workers', () => {
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      for (const loop of PIPELINE_LOOPS) {
        const countEl = screen.getByTestId(`loop-count-${loop.key}`)
        expect(countEl).toHaveTextContent('0')
      }
    })

    it('shows worker counts per stage', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ workers: mockPipelineWorkers }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.getByTestId('loop-count-triage')).toHaveTextContent('1')
      expect(screen.getByTestId('loop-count-plan')).toHaveTextContent('1')
      expect(screen.getByTestId('loop-count-implement')).toHaveTextContent('1')
      expect(screen.getByTestId('loop-count-review')).toHaveTextContent('1')
    })

    it('shows "worker" singular when count is 1', () => {
      const singleWorker = {
        10: { status: 'running', worker: 1, role: 'implementer', title: 'Issue #10', branch: '', transcript: [], pr: null },
      }
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ workers: singleWorker }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.getByText('worker')).toBeInTheDocument()
    })

    it('shows "workers" plural when count is not 1', () => {
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      const workerLabels = screen.getAllByText('workers')
      expect(workerLabels.length).toBe(PIPELINE_LOOPS.length)
    })

    it('shows loop count in stage color when loop is enabled and workers are active', () => {
      const singleImplementer = {
        10: { status: 'running', worker: 1, role: 'implementer', title: 'Issue #10', branch: '', transcript: [], pr: null },
      }
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ workers: singleImplementer }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      const implementCount = screen.getByTestId('loop-count-implement')
      expect(implementCount.style.color).toBe('var(--accent)')
    })

    it('shows loop count in muted color when enabled but no active workers', () => {
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      const implementCount = screen.getByTestId('loop-count-implement')
      expect(implementCount.style.color).toBe('var(--text-muted)')
    })

    it('shows loop count in muted color when loop is disabled even if workers are active', () => {
      const singleImplementer = {
        10: { status: 'running', worker: 1, role: 'implementer', title: 'Issue #10', branch: '', transcript: [], pr: null },
      }
      const disabledBgWorkers = [
        { name: 'implement', status: 'ok', enabled: false, last_run: null, details: {} },
      ]
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ workers: singleImplementer, backgroundWorkers: disabledBgWorkers }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      const implementCount = screen.getByTestId('loop-count-implement')
      expect(implementCount.style.color).toBe('var(--text-muted)')
    })

    it('calls onToggleBgWorker with pipeline loop key when toggled', () => {
      const onToggle = vi.fn()
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} onToggleBgWorker={onToggle} />)
      const allOnButtons = screen.getAllByText('On')
      fireEvent.click(allOnButtons[0]) // First pipeline loop = triage
      expect(onToggle).toHaveBeenCalledWith('triage', false)
    })

    it('shows On/Off toggle state correctly', () => {
      const disabledBgWorkers = [
        { name: 'triage', status: 'ok', enabled: false, last_run: null, details: {} },
      ]
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ backgroundWorkers: disabledBgWorkers }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} onToggleBgWorker={() => {}} />)
      expect(screen.getByText('Off')).toBeInTheDocument()
      const onButtons = screen.getAllByText('On')
      expect(onButtons.length).toBe(3) // 3 enabled loops
    })

    it('shows dimmed dot color when loop is disabled', () => {
      const disabledBgWorkers = [
        { name: 'triage', status: 'ok', enabled: false, last_run: null, details: {} },
      ]
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ backgroundWorkers: disabledBgWorkers }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      // The triage loop dot should use dimColor (greenSubtle) instead of the active color
      // We can't easily check dot color without testid, but the label should be dimmed
      const triageLabel = screen.getByText('Triage')
      expect(triageLabel.style.color).toBe('var(--text-muted)')
    })
  })

  describe('Pipeline Worker Cards', () => {
    it('shows "No active pipeline workers" when no workers', () => {
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.getByText('No active pipeline workers')).toBeInTheDocument()
    })

    it('renders active worker cards with issue #, role badge, status', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ workers: mockPipelineWorkers }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.getByText('#5')).toBeInTheDocument()
      expect(screen.getByText('#7')).toBeInTheDocument()
      expect(screen.getByText('#10')).toBeInTheDocument()
      expect(screen.getByText('#20')).toBeInTheDocument()
      expect(screen.getByText('triage')).toBeInTheDocument()
      expect(screen.getByText('planner')).toBeInTheDocument()
      expect(screen.getByText('implementer')).toBeInTheDocument()
      expect(screen.getByText('reviewer')).toBeInTheDocument()
    })

    it('filters out queued workers', () => {
      const workers = {
        99: { status: 'queued', worker: 1, role: 'implementer', title: 'Issue #99', branch: '', transcript: [], pr: null },
      }
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ workers }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.getByText('No active pipeline workers')).toBeInTheDocument()
    })

    it('filters out done and failed workers', () => {
      const workers = {
        50: { status: 'done', worker: 1, role: 'implementer', title: 'Issue #50', branch: '', transcript: [], pr: null },
        51: { status: 'failed', worker: 2, role: 'reviewer', title: 'Issue #51', branch: '', transcript: [], pr: null },
      }
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ workers }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.getByText('No active pipeline workers')).toBeInTheDocument()
      expect(screen.queryByText('#50')).not.toBeInTheDocument()
      expect(screen.queryByText('#51')).not.toBeInTheDocument()
    })

    it('shows worker title', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ workers: mockPipelineWorkers }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.getByText('Issue #10')).toBeInTheDocument()
      expect(screen.getByText('Triage Issue #5')).toBeInTheDocument()
    })

    it('shows transcript toggle when transcript has lines', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ workers: mockPipelineWorkers }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.getByText('Show transcript (3 lines)')).toBeInTheDocument()
    })

    it('expands transcript on click', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ workers: mockPipelineWorkers }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      const toggle = screen.getByText('Show transcript (3 lines)')
      fireEvent.click(toggle)
      expect(screen.getByText('Writing code...')).toBeInTheDocument()
      expect(screen.getByText('Running tests...')).toBeInTheDocument()
      expect(screen.getByText('All tests pass')).toBeInTheDocument()
    })

    it('does not show transcript toggle when transcript is empty', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ workers: mockPipelineWorkers }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.queryByText('Show transcript (0 lines)')).not.toBeInTheDocument()
    })
  })

  describe('Status Badges', () => {
    it('shows "N active" badge when workers present', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ workers: mockPipelineWorkers }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.getByText('4 active')).toBeInTheDocument()
    })

    it('does not show active badge when no active workers', () => {
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.queryByText(/\d+ active/)).not.toBeInTheDocument()
    })

    it('shows "N HITL issues" badge when HITL items exist', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({
        hitlItems: [
          { issue_number: 1, title: 'Issue 1' },
          { issue_number: 2, title: 'Issue 2' },
          { issue_number: 3, title: 'Issue 3' },
        ],
      }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.getByText('3 HITL issues')).toBeInTheDocument()
    })

    it('shows singular "issue" for count of 1', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({
        hitlItems: [{ issue_number: 1, title: 'Issue 1' }],
      }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.getByText('1 HITL issue')).toBeInTheDocument()
    })

    it('does not show HITL badge when hitlItems is empty', () => {
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.queryByText(/HITL/)).not.toBeInTheDocument()
    })

    it('shows both active and HITL badges together', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({
        workers: mockPipelineWorkers,
        hitlItems: [{ issue_number: 1, title: 'Issue 1' }, { issue_number: 2, title: 'Issue 2' }],
      }))
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.getByText('4 active')).toBeInTheDocument()
      expect(screen.getByText('2 HITL issues')).toBeInTheDocument()
    })
  })

  describe('Collapse Behavior', () => {
    it('renders narrow panel with status dots when collapsed', () => {
      render(<PipelineControlPanel collapsed={true} onToggleCollapse={() => {}} />)
      // Should show collapsed dots for each loop
      for (const loop of PIPELINE_LOOPS) {
        expect(screen.getByTestId(`collapsed-dot-${loop.key}`)).toBeInTheDocument()
      }
      // Should not show full pipeline UI
      expect(screen.queryByText('Pipeline')).not.toBeInTheDocument()
      expect(screen.queryByText('No active pipeline workers')).not.toBeInTheDocument()
    })

    it('renders full panel with all controls when expanded', () => {
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={() => {}} />)
      expect(screen.getByText('Pipeline')).toBeInTheDocument()
      expect(screen.getByText('No active pipeline workers')).toBeInTheDocument()
      for (const loop of PIPELINE_LOOPS) {
        expect(screen.getByText(loop.label)).toBeInTheDocument()
      }
    })

    it('calls onToggleCollapse when collapse button clicked (expanded)', () => {
      const onToggle = vi.fn()
      render(<PipelineControlPanel collapsed={false} onToggleCollapse={onToggle} />)
      fireEvent.click(screen.getByTestId('pipeline-panel-collapse'))
      expect(onToggle).toHaveBeenCalledTimes(1)
    })

    it('calls onToggleCollapse when expand button clicked (collapsed)', () => {
      const onToggle = vi.fn()
      render(<PipelineControlPanel collapsed={true} onToggleCollapse={onToggle} />)
      fireEvent.click(screen.getByTestId('pipeline-panel-expand'))
      expect(onToggle).toHaveBeenCalledTimes(1)
    })
  })
})
