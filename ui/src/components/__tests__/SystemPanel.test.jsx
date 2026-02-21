import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { BACKGROUND_WORKERS, PIPELINE_LOOPS } from '../../constants'

const mockUseHydra = vi.fn()

vi.mock('../../context/HydraContext', () => ({
  useHydra: (...args) => mockUseHydra(...args),
}))

// Import SystemPanel after mock is set up
const { SystemPanel } = await import('../SystemPanel')

beforeEach(() => {
  mockUseHydra.mockReturnValue({ pipelinePollerLastRun: null, hitlItems: [], pipelineIssues: {}, orchestratorStatus: 'idle' })
})

const mockBgWorkers = [
  { name: 'triage', status: 'ok', enabled: true, last_run: null, details: {} },
  { name: 'plan', status: 'ok', enabled: true, last_run: null, details: {} },
  { name: 'implement', status: 'ok', enabled: true, last_run: null, details: {} },
  { name: 'review', status: 'ok', enabled: true, last_run: null, details: {} },
  { name: 'memory_sync', status: 'ok', enabled: true, last_run: new Date().toISOString(), details: { item_count: 12, digest_chars: 2400 } },
  { name: 'retrospective', status: 'error', enabled: true, last_run: '2026-02-20T10:28:00Z', details: { last_issue: 42 } },
  { name: 'metrics', status: 'ok', enabled: true, last_run: '2026-02-20T10:25:00Z', details: {} },
  { name: 'review_insights', status: 'disabled', enabled: false, last_run: null, details: {} },
]

const mockPipelineWorkers = {
  'triage-5': { status: 'evaluating', worker: 1, role: 'triage', title: 'Triage Issue #5', branch: '', transcript: ['Evaluating issue...', 'Checking labels'], pr: null },
  'plan-7': { status: 'planning', worker: 2, role: 'planner', title: 'Plan Issue #7', branch: '', transcript: ['Reading codebase...'], pr: null },
  10: { status: 'running', worker: 3, role: 'implementer', title: 'Issue #10', branch: 'agent/issue-10', transcript: ['Writing code...', 'Running tests...', 'All tests pass'], pr: null },
  'review-20': { status: 'reviewing', worker: 4, role: 'reviewer', title: 'PR #20 (Issue #3)', branch: '', transcript: [], pr: 20 },
}

describe('SystemPanel', () => {
  describe('Background Workers', () => {
    it('renders all background worker cards (including system workers)', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      for (const def of BACKGROUND_WORKERS) {
        expect(screen.getByText(def.label)).toBeInTheDocument()
      }
    })

    it('shows correct status dot color for ok workers when orchestrator running', () => {
      mockUseHydra.mockReturnValue({ pipelinePollerLastRun: null, hitlItems: [], pipelineIssues: {}, orchestratorStatus: 'running' })
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      const dot = screen.getByTestId('dot-memory_sync')
      expect(dot.style.background).toBe('var(--green)')
    })

    it('shows correct status dot color for error workers when orchestrator running', () => {
      mockUseHydra.mockReturnValue({ pipelinePollerLastRun: null, hitlItems: [], pipelineIssues: {}, orchestratorStatus: 'running' })
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      const dot = screen.getByTestId('dot-retrospective')
      expect(dot.style.background).toBe('var(--red)')
    })

    it('shows "idle" (yellow) for enabled non-system workers and "stopped" (red) for system workers when orchestrator not running', () => {
      // Default mock has orchestratorStatus: 'idle'
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      const nonSystem = BACKGROUND_WORKERS.filter(w => !w.system)
      const systemWorkers = BACKGROUND_WORKERS.filter(w => w.system)
      // Non-system workers with no state default to enabled — show idle with yellow dot
      const idleTexts = screen.getAllByText('idle')
      expect(idleTexts.length).toBe(nonSystem.length)
      for (const def of nonSystem) {
        const dot = screen.getByTestId(`dot-${def.key}`)
        expect(dot.style.background).toBe('var(--yellow)')
      }
      // System workers show stopped with red dot
      const stoppedTexts = screen.getAllByText('stopped')
      expect(stoppedTexts.length).toBe(systemWorkers.length)
      for (const def of systemWorkers) {
        const dot = screen.getByTestId(`dot-${def.key}`)
        expect(dot.style.background).toBe('var(--red)')
      }
    })

    it('shows ok/error status when orchestrator is running', () => {
      mockUseHydra.mockReturnValue({
        pipelinePollerLastRun: '2026-02-20T10:00:00Z',
        hitlItems: [],
        pipelineIssues: {},
        orchestratorStatus: 'running',
      })
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      // memory_sync has ok status
      const okDot = screen.getByTestId('dot-memory_sync')
      expect(okDot.style.background).toBe('var(--green)')
      // retrospective has error status
      const errDot = screen.getByTestId('dot-retrospective')
      expect(errDot.style.background).toBe('var(--red)')
      // review_insights disabled -> off (red)
      const offDot = screen.getByTestId('dot-review_insights')
      expect(offDot.style.background).toBe('var(--red)')
    })

    it('shows last run time when available', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      expect(screen.getAllByText(/Last run:/).length).toBeGreaterThanOrEqual(BACKGROUND_WORKERS.length)
    })

    it('shows "never" for workers that have not run', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      const neverTexts = screen.getAllByText(/never/)
      expect(neverTexts.length).toBeGreaterThanOrEqual(BACKGROUND_WORKERS.length)
    })

    it('shows detail key-value pairs', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      expect(screen.getByText('item count')).toBeInTheDocument()
      expect(screen.getByText('12')).toBeInTheDocument()
      expect(screen.getByText('digest chars')).toBeInTheDocument()
      expect(screen.getByText('2400')).toBeInTheDocument()
    })

    it('shows system badge on system workers', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      const badges = screen.getAllByText('system')
      const systemWorkerCount = BACKGROUND_WORKERS.filter(w => w.system).length
      expect(badges.length).toBe(systemWorkerCount)
    })

    it('shows system worker status as colored pill (green for ok) when orchestrator running', () => {
      mockUseHydra.mockReturnValue({ pipelinePollerLastRun: null, hitlItems: [], pipelineIssues: {}, orchestratorStatus: 'running' })
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      // memory_sync has status ok — green pill
      const okPill = screen.getByTestId('status-pill-memory_sync')
      expect(okPill).toHaveTextContent('ok')
      expect(okPill.style.color).toBe('var(--green)')
      expect(okPill.style.background).toBe('var(--green-subtle)')
      // metrics has status ok — green pill
      const metricsPill = screen.getByTestId('status-pill-metrics')
      expect(metricsPill).toHaveTextContent('ok')
      expect(metricsPill.style.color).toBe('var(--green)')
    })

    it('shows red pill for stopped system workers', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      // No backend state — all system workers should show stopped (red pill)
      const pollerPill = screen.getByTestId('status-pill-pipeline_poller')
      expect(pollerPill).toHaveTextContent('stopped')
      expect(pollerPill.style.color).toBe('var(--red)')
      expect(pollerPill.style.background).toBe('var(--red-subtle)')
    })
  })

  describe('Error Display', () => {
    it('shows error details with red styling when status is error', () => {
      mockUseHydra.mockReturnValue({ pipelinePollerLastRun: null, hitlItems: [], pipelineIssues: {}, orchestratorStatus: 'running' })
      const errorWorkers = [
        { name: 'retrospective', status: 'error', enabled: true, last_run: '2026-02-20T10:28:00Z', details: { error: 'Connection timeout', retries: 3 } },
      ]
      render(<SystemPanel workers={{}} backgroundWorkers={errorWorkers} />)
      expect(screen.getByText('Connection timeout')).toBeInTheDocument()
      expect(screen.getByText('3')).toBeInTheDocument()
    })

    it('shows error key in details section', () => {
      mockUseHydra.mockReturnValue({ pipelinePollerLastRun: null, hitlItems: [], pipelineIssues: {}, orchestratorStatus: 'running' })
      const errorWorkers = [
        { name: 'retrospective', status: 'error', enabled: true, last_run: null, details: { error: 'API rate limited' } },
      ]
      render(<SystemPanel workers={{}} backgroundWorkers={errorWorkers} />)
      expect(screen.getByText('API rate limited')).toBeInTheDocument()
      // The word "error" appears as both status text and detail key
      const errorTexts = screen.getAllByText('error')
      expect(errorTexts.length).toBeGreaterThanOrEqual(2)
    })
  })

  describe('Pipeline Workers', () => {
    it('shows "No active pipeline workers" when no workers', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      expect(screen.getByText('No active pipeline workers')).toBeInTheDocument()
    })

    it('renders pipeline worker cards', () => {
      render(<SystemPanel workers={mockPipelineWorkers} backgroundWorkers={[]} />)
      expect(screen.getByText('Pipeline')).toBeInTheDocument()
      expect(screen.getByText('#5')).toBeInTheDocument()
      expect(screen.getByText('#7')).toBeInTheDocument()
      expect(screen.getByText('#10')).toBeInTheDocument()
      expect(screen.getByText('#20')).toBeInTheDocument()
    })

    it('shows role badges for pipeline workers', () => {
      render(<SystemPanel workers={mockPipelineWorkers} backgroundWorkers={[]} />)
      expect(screen.getByText('triage')).toBeInTheDocument()
      expect(screen.getByText('planner')).toBeInTheDocument()
      expect(screen.getByText('implementer')).toBeInTheDocument()
      expect(screen.getByText('reviewer')).toBeInTheDocument()
    })

    it('shows worker title', () => {
      render(<SystemPanel workers={mockPipelineWorkers} backgroundWorkers={[]} />)
      expect(screen.getByText('Issue #10')).toBeInTheDocument()
      expect(screen.getByText('Triage Issue #5')).toBeInTheDocument()
    })

    it('shows transcript toggle when transcript has lines', () => {
      render(<SystemPanel workers={mockPipelineWorkers} backgroundWorkers={[]} />)
      expect(screen.getByText('Show transcript (3 lines)')).toBeInTheDocument()
    })

    it('expands transcript on click', () => {
      render(<SystemPanel workers={mockPipelineWorkers} backgroundWorkers={[]} />)
      const toggle = screen.getByText('Show transcript (3 lines)')
      fireEvent.click(toggle)
      expect(screen.getByText('Writing code...')).toBeInTheDocument()
      expect(screen.getByText('Running tests...')).toBeInTheDocument()
      expect(screen.getByText('All tests pass')).toBeInTheDocument()
    })

    it('does not show transcript toggle when transcript is empty', () => {
      render(<SystemPanel workers={mockPipelineWorkers} backgroundWorkers={[]} />)
      expect(screen.queryByText('Show transcript (0 lines)')).not.toBeInTheDocument()
    })

    it('filters out queued workers', () => {
      const workers = {
        99: { status: 'queued', worker: 1, role: 'implementer', title: 'Issue #99', branch: '', transcript: [], pr: null },
      }
      render(<SystemPanel workers={workers} backgroundWorkers={[]} />)
      expect(screen.getByText('No active pipeline workers')).toBeInTheDocument()
    })
  })

  describe('Pipeline Loop Toggles', () => {
    it('shows pipeline loop toggle chips in the Pipeline section', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} onToggleBgWorker={() => {}} />)
      for (const loop of PIPELINE_LOOPS) {
        expect(screen.getByText(loop.label)).toBeInTheDocument()
      }
    })

    it('always shows issue count on pipeline loop chips (even zero)', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      for (const loop of PIPELINE_LOOPS) {
        const countEl = screen.getByTestId(`loop-count-${loop.key}`)
        expect(countEl).toHaveTextContent('0')
      }
    })

    it('shows pipeline issue counts from pipelineIssues context', () => {
      mockUseHydra.mockReturnValue({
        pipelinePollerLastRun: null,
        hitlItems: [],
        pipelineIssues: {
          triage: [{ issue_number: 1 }, { issue_number: 2 }],
          plan: [{ issue_number: 3 }],
          implement: [],
          review: [{ issue_number: 4 }, { issue_number: 5 }, { issue_number: 6 }],
        },
      })
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      expect(screen.getByTestId('loop-count-triage')).toHaveTextContent('2')
      expect(screen.getByTestId('loop-count-plan')).toHaveTextContent('1')
      expect(screen.getByTestId('loop-count-implement')).toHaveTextContent('0')
      expect(screen.getByTestId('loop-count-review')).toHaveTextContent('3')
    })

    it('shows active worker count on pipeline loop chips when workers are active', () => {
      render(<SystemPanel workers={mockPipelineWorkers} backgroundWorkers={[]} onToggleBgWorker={() => {}} />)
      // mockPipelineWorkers has 1 triage, 1 planner, 1 implementer, 1 reviewer
      const activeLabels = screen.getAllByText('1 active')
      expect(activeLabels.length).toBe(4)
    })

    it('calls onToggleBgWorker with pipeline loop key when toggled', () => {
      const onToggle = vi.fn()
      mockUseHydra.mockReturnValue({ pipelinePollerLastRun: null, hitlItems: [], pipelineIssues: {}, orchestratorStatus: 'running' })
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onToggleBgWorker={onToggle} />)
      const allOnButtons = screen.getAllByText('On')
      fireEvent.click(allOnButtons[0]) // First pipeline loop = triage
      expect(onToggle).toHaveBeenCalledWith('triage', false)
    })
  })

  describe('Background Worker Toggles', () => {
    it('shows toggle buttons for non-system workers only when onToggleBgWorker provided', () => {
      mockUseHydra.mockReturnValue({ pipelinePollerLastRun: null, hitlItems: [], pipelineIssues: {}, orchestratorStatus: 'running' })
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onToggleBgWorker={() => {}} />)
      const onButtons = screen.getAllByText('On')
      // Pipeline loops (4) + non-system background workers that are enabled
      const nonSystemEnabled = BACKGROUND_WORKERS.filter(def => {
        if (def.system) return false
        const state = mockBgWorkers.find(w => w.name === def.key)
        return state?.enabled !== false
      }).length
      const enabledLoopCount = PIPELINE_LOOPS.length
      expect(onButtons.length).toBe(enabledLoopCount + nonSystemEnabled)
    })

    it('system workers do not show toggle buttons', () => {
      mockUseHydra.mockReturnValue({ pipelinePollerLastRun: null, hitlItems: [], pipelineIssues: {}, orchestratorStatus: 'running' })
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onToggleBgWorker={() => {}} />)
      expect(screen.getByText('Pipeline Poller')).toBeInTheDocument()
      expect(screen.getByText('Memory Sync')).toBeInTheDocument()
      expect(screen.getByText('Metrics')).toBeInTheDocument()
      // Count On/Off buttons — should only be loops + non-system bg workers
      const allToggleButtons = [...screen.getAllByText('On'), ...screen.getAllByText('Off')]
      const nonSystemBgCount = BACKGROUND_WORKERS.filter(w => !w.system).length
      expect(allToggleButtons.length).toBe(PIPELINE_LOOPS.length + nonSystemBgCount)
    })

    it('does not show toggle buttons when onToggleBgWorker is not provided', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      expect(screen.queryByText('On')).not.toBeInTheDocument()
      expect(screen.queryByText('Off')).not.toBeInTheDocument()
    })

    it('shows Off button for disabled workers when orchestrator running', () => {
      const onToggle = vi.fn()
      mockUseHydra.mockReturnValue({ pipelinePollerLastRun: null, hitlItems: [], pipelineIssues: {}, orchestratorStatus: 'running' })
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onToggleBgWorker={onToggle} />)
      expect(screen.getByText('Off')).toBeInTheDocument()
    })

    it('clicking Off toggles to enabled', () => {
      const onToggle = vi.fn()
      mockUseHydra.mockReturnValue({ pipelinePollerLastRun: null, hitlItems: [], pipelineIssues: {}, orchestratorStatus: 'running' })
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onToggleBgWorker={onToggle} />)
      fireEvent.click(screen.getByText('Off'))
      expect(onToggle).toHaveBeenCalledWith('review_insights', true)
    })

    it('non-system workers show On when orchestrator running and no state reported', () => {
      const onToggle = vi.fn()
      mockUseHydra.mockReturnValue({ pipelinePollerLastRun: null, hitlItems: [], pipelineIssues: {}, orchestratorStatus: 'running' })
      render(<SystemPanel workers={{}} backgroundWorkers={[]} onToggleBgWorker={onToggle} />)
      const onButtons = screen.getAllByText('On')
      const nonSystemCount = BACKGROUND_WORKERS.filter(w => !w.system).length
      // Pipeline loops + non-system background workers
      expect(onButtons.length).toBe(PIPELINE_LOOPS.length + nonSystemCount)
    })

    it('non-system workers show On (default enabled) when orchestrator not running and no state', () => {
      const onToggle = vi.fn()
      render(<SystemPanel workers={{}} backgroundWorkers={[]} onToggleBgWorker={onToggle} />)
      // Non-system bg workers default to enabled — show On even when orchestrator is off
      const onButtons = screen.getAllByText('On')
      const nonSystemCount = BACKGROUND_WORKERS.filter(w => !w.system).length
      // Pipeline loops (4) + non-system background workers
      expect(onButtons.length).toBe(PIPELINE_LOOPS.length + nonSystemCount)
    })

    it('non-system workers show Off when explicitly disabled and orchestrator not running', () => {
      const onToggle = vi.fn()
      const disabledWorkers = [
        { name: 'retrospective', status: 'ok', enabled: false, last_run: null, details: {} },
        { name: 'review_insights', status: 'ok', enabled: false, last_run: null, details: {} },
      ]
      render(<SystemPanel workers={{}} backgroundWorkers={disabledWorkers} onToggleBgWorker={onToggle} />)
      const offButtons = screen.getAllByText('Off')
      expect(offButtons.length).toBe(2)
    })
  })

  describe('HITL Count', () => {
    it('does not show HITL badge when hitlItems is empty', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      expect(screen.queryByText(/HITL/)).not.toBeInTheDocument()
    })

    it('shows HITL count when hitlItems is non-empty', () => {
      mockUseHydra.mockReturnValue({
        pipelinePollerLastRun: null,
        hitlItems: [
          { issue_number: 1, title: 'Issue 1' },
          { issue_number: 2, title: 'Issue 2' },
          { issue_number: 3, title: 'Issue 3' },
        ],
        pipelineIssues: {},
      })
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      expect(screen.getByText('3 HITL issues')).toBeInTheDocument()
    })

    it('shows singular "issue" for count of 1', () => {
      mockUseHydra.mockReturnValue({
        pipelinePollerLastRun: null,
        hitlItems: [{ issue_number: 1, title: 'Issue 1' }],
        pipelineIssues: {},
      })
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      expect(screen.getByText('1 HITL issue')).toBeInTheDocument()
    })
  })

  describe('Pipeline Poller status', () => {
    it('shows green dot and ok when orchestrator is running and poller has run', () => {
      mockUseHydra.mockReturnValue({
        pipelinePollerLastRun: '2026-02-20T10:00:00Z',
        hitlItems: [],
        pipelineIssues: {},
        orchestratorStatus: 'running',
      })
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      const dot = screen.getByTestId('dot-pipeline_poller')
      expect(dot.style.background).toBe('var(--green)')
    })

    it('shows red stopped when orchestrator is not running even if poller has lastRun', () => {
      mockUseHydra.mockReturnValue({
        pipelinePollerLastRun: '2026-02-20T10:00:00Z',
        hitlItems: [],
        pipelineIssues: {},
        orchestratorStatus: 'idle',
      })
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      const dot = screen.getByTestId('dot-pipeline_poller')
      expect(dot.style.background).toBe('var(--red)')
    })

    it('shows red stopped when pipeline poller has not run', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      const dot = screen.getByTestId('dot-pipeline_poller')
      expect(dot.style.background).toBe('var(--red)')
    })
  })
})
