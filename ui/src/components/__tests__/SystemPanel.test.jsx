import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { BACKGROUND_WORKERS, PIPELINE_LOOPS } from '../../constants'
import { deriveStageStatus } from '../../hooks/useStageStatus'

const mockUseHydraFlow = vi.fn()

vi.mock('../../context/HydraFlowContext', () => ({
  useHydraFlow: (...args) => mockUseHydraFlow(...args),
}))

// Import SystemPanel after mock is set up
const { SystemPanel } = await import('../SystemPanel')

function defaultMockContext(overrides = {}) {
  const pipelineIssues = overrides.pipelineIssues || {}
  const workers = overrides.workers || {}
  const backgroundWorkers = overrides.backgroundWorkers || []
  return {
    pipelinePollerLastRun: null,
    hitlItems: [],
    orchestratorStatus: 'idle',
    stageStatus: deriveStageStatus(pipelineIssues, workers, backgroundWorkers, {}),
    events: [],
    ...overrides,
  }
}

beforeEach(() => {
  mockUseHydraFlow.mockReturnValue(defaultMockContext())
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
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ orchestratorStatus: 'running' }))
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      const dot = screen.getByTestId('dot-memory_sync')
      expect(dot.style.background).toBe('var(--green)')
    })

    it('shows correct status dot color for error workers when orchestrator running', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ orchestratorStatus: 'running' }))
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
      mockUseHydraFlow.mockReturnValue(defaultMockContext({
        pipelinePollerLastRun: '2026-02-20T10:00:00Z',
        orchestratorStatus: 'running',
      }))
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
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ orchestratorStatus: 'running' }))
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
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ orchestratorStatus: 'running' }))
      const errorWorkers = [
        { name: 'retrospective', status: 'error', enabled: true, last_run: '2026-02-20T10:28:00Z', details: { error: 'Connection timeout', retries: 3 } },
      ]
      render(<SystemPanel workers={{}} backgroundWorkers={errorWorkers} />)
      expect(screen.getByText('Connection timeout')).toBeInTheDocument()
      expect(screen.getByText('3')).toBeInTheDocument()
    })

    it('shows error key in details section', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ orchestratorStatus: 'running' }))
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

    it('filters out done and failed workers from pipeline cards', () => {
      const workers = {
        50: { status: 'done', worker: 1, role: 'implementer', title: 'Issue #50', branch: '', transcript: [], pr: null },
        51: { status: 'failed', worker: 2, role: 'reviewer', title: 'Issue #51', branch: '', transcript: [], pr: null },
        52: { status: 'escalated', worker: 3, role: 'planner', title: 'Issue #52', branch: '', transcript: [], pr: null },
      }
      render(<SystemPanel workers={workers} backgroundWorkers={[]} />)
      expect(screen.getByText('No active pipeline workers')).toBeInTheDocument()
      expect(screen.queryByText('#50')).not.toBeInTheDocument()
      expect(screen.queryByText('#51')).not.toBeInTheDocument()
      expect(screen.queryByText('#52')).not.toBeInTheDocument()
    })
  })

  describe('Pipeline Loop Toggles', () => {
    it('shows pipeline loop toggle chips in the Pipeline section', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} onToggleBgWorker={() => {}} />)
      for (const loop of PIPELINE_LOOPS) {
        expect(screen.getByText(loop.label)).toBeInTheDocument()
      }
    })

    it('shows worker count of 0 when no active workers', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      for (const loop of PIPELINE_LOOPS) {
        const countEl = screen.getByTestId(`loop-count-${loop.key}`)
        expect(countEl).toHaveTextContent('0')
      }
    })

    it('shows worker counts per stage on pipeline loop chips', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ workers: mockPipelineWorkers }))
      render(<SystemPanel workers={mockPipelineWorkers} backgroundWorkers={[]} />)
      // mockPipelineWorkers has 1 triage, 1 planner, 1 implementer, 1 reviewer
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
      render(<SystemPanel workers={singleWorker} backgroundWorkers={[]} />)
      expect(screen.getByText('worker')).toBeInTheDocument()
    })

    it('shows "workers" plural when count is not 1', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      // All stages have 0 workers — should all show "workers"
      const workerLabels = screen.getAllByText('workers')
      expect(workerLabels.length).toBe(PIPELINE_LOOPS.length)
    })

    it('shows loop count in stage color when loop is enabled and workers are active', () => {
      const singleImplementer = {
        10: { status: 'running', worker: 1, role: 'implementer', title: 'Issue #10', branch: '', transcript: [], pr: null },
      }
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ workers: singleImplementer }))
      render(<SystemPanel workers={singleImplementer} backgroundWorkers={[]} />)
      const implementCount = screen.getByTestId('loop-count-implement')
      expect(implementCount.style.color).toBe('var(--accent)')
    })

    it('shows loop count in muted color when enabled but no active workers', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
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
      render(<SystemPanel workers={singleImplementer} backgroundWorkers={disabledBgWorkers} />)
      const implementCount = screen.getByTestId('loop-count-implement')
      expect(implementCount.style.color).toBe('var(--text-muted)')
    })

    it('calls onToggleBgWorker with pipeline loop key when toggled', () => {
      const onToggle = vi.fn()
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ orchestratorStatus: 'running', backgroundWorkers: mockBgWorkers }))
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onToggleBgWorker={onToggle} />)
      const allOnButtons = screen.getAllByText('On')
      fireEvent.click(allOnButtons[0]) // First pipeline loop = triage
      expect(onToggle).toHaveBeenCalledWith('triage', false)
    })
  })

  describe('Background Worker Toggles', () => {
    it('shows toggle buttons for non-system workers only when onToggleBgWorker provided', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ orchestratorStatus: 'running', backgroundWorkers: mockBgWorkers }))
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
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ orchestratorStatus: 'running', backgroundWorkers: mockBgWorkers }))
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onToggleBgWorker={() => {}} />)
      expect(screen.getByText('Pipeline Poller')).toBeInTheDocument()
      expect(screen.getByText('Memory Manager')).toBeInTheDocument()
      expect(screen.getByText('Metrics Munger')).toBeInTheDocument()
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
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ orchestratorStatus: 'running', backgroundWorkers: mockBgWorkers }))
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onToggleBgWorker={onToggle} />)
      expect(screen.getByText('Off')).toBeInTheDocument()
    })

    it('clicking Off toggles to enabled', () => {
      const onToggle = vi.fn()
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ orchestratorStatus: 'running', backgroundWorkers: mockBgWorkers }))
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onToggleBgWorker={onToggle} />)
      fireEvent.click(screen.getByText('Off'))
      expect(onToggle).toHaveBeenCalledWith('review_insights', true)
    })

    it('non-system workers show On when orchestrator running and no state reported', () => {
      const onToggle = vi.fn()
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ orchestratorStatus: 'running' }))
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
      mockUseHydraFlow.mockReturnValue(defaultMockContext({ backgroundWorkers: disabledWorkers }))
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
      mockUseHydraFlow.mockReturnValue(defaultMockContext({
        hitlItems: [
          { issue_number: 1, title: 'Issue 1' },
          { issue_number: 2, title: 'Issue 2' },
          { issue_number: 3, title: 'Issue 3' },
        ],
      }))
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      expect(screen.getByText('3 HITL issues')).toBeInTheDocument()
    })

    it('shows singular "issue" for count of 1', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({
        hitlItems: [{ issue_number: 1, title: 'Issue 1' }],
      }))
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      expect(screen.getByText('1 HITL issue')).toBeInTheDocument()
    })
  })

  describe('Total Active Pill', () => {
    it('shows total active pill when pipeline workers are active', () => {
      render(<SystemPanel workers={mockPipelineWorkers} backgroundWorkers={[]} />)
      expect(screen.getByText('4 active')).toBeInTheDocument()
    })

    it('does not show total active pill when no active workers', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      expect(screen.queryByText(/\d+ active/)).not.toBeInTheDocument()
    })

    it('shows total active pill alongside HITL badge', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({
        hitlItems: [{ issue_number: 1, title: 'Issue 1' }, { issue_number: 2, title: 'Issue 2' }],
        orchestratorStatus: 'running',
      }))
      render(<SystemPanel workers={mockPipelineWorkers} backgroundWorkers={[]} />)
      expect(screen.getByText('4 active')).toBeInTheDocument()
      expect(screen.getByText('2 HITL issues')).toBeInTheDocument()
    })

    it('shows HITL badge without active pill when no active workers', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({
        hitlItems: [{ issue_number: 1, title: 'Issue 1' }],
      }))
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      expect(screen.queryByText(/\d+ active/)).not.toBeInTheDocument()
      expect(screen.getByText('1 HITL issue')).toBeInTheDocument()
      expect(screen.getByText('No active pipeline workers')).toBeInTheDocument()
    })
  })

  describe('Pipeline Poller status', () => {
    it('shows green dot and ok when orchestrator is running and poller has run', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({
        pipelinePollerLastRun: '2026-02-20T10:00:00Z',
        orchestratorStatus: 'running',
      }))
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      const dot = screen.getByTestId('dot-pipeline_poller')
      expect(dot.style.background).toBe('var(--green)')
    })

    it('shows red stopped when orchestrator is not running even if poller has lastRun', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({
        pipelinePollerLastRun: '2026-02-20T10:00:00Z',
        orchestratorStatus: 'idle',
      }))
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

  describe('Sub-tab Navigation', () => {
    it('shows Workers and Livestream sub-tab labels', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      expect(screen.getByText('Workers')).toBeInTheDocument()
      expect(screen.getByText('Livestream')).toBeInTheDocument()
    })

    it('Workers sub-tab is active by default showing pipeline content', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      expect(screen.getByText('Pipeline')).toBeInTheDocument()
      expect(screen.getByText('Background Workers')).toBeInTheDocument()
    })

    it('clicking Livestream sub-tab shows event stream', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      fireEvent.click(screen.getByText('Livestream'))
      expect(screen.getByText('Waiting for events...')).toBeInTheDocument()
      // Pipeline content should not be visible
      expect(screen.queryByText('Pipeline')).not.toBeInTheDocument()
    })

    it('clicking Workers sub-tab returns to worker content', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      fireEvent.click(screen.getByText('Livestream'))
      expect(screen.queryByText('Pipeline')).not.toBeInTheDocument()
      fireEvent.click(screen.getByText('Workers'))
      expect(screen.getByText('Pipeline')).toBeInTheDocument()
    })

    it('active sub-tab has accent color styling', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      const workersTab = screen.getByText('Workers')
      expect(workersTab.style.color).toBe('var(--accent)')
      expect(workersTab.style.borderLeftColor).toBe('var(--accent)')
      const livestreamTab = screen.getByText('Livestream')
      expect(livestreamTab.style.color).toBe('var(--text-muted)')
      expect(livestreamTab.style.borderLeftColor).toBe('transparent')
    })

    it('sub-tab styles swap when clicking Livestream', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      fireEvent.click(screen.getByText('Livestream'))
      expect(screen.getByText('Livestream').style.color).toBe('var(--accent)')
      expect(screen.getByText('Livestream').style.borderLeftColor).toBe('var(--accent)')
      expect(screen.getByText('Workers').style.color).toBe('var(--text-muted)')
      expect(screen.getByText('Workers').style.borderLeftColor).toBe('transparent')
    })

    it('renders event data in Livestream sub-tab', () => {
      mockUseHydraFlow.mockReturnValue(defaultMockContext({
        events: [
          { timestamp: new Date().toISOString(), type: 'worker_update', data: { issue: 1, status: 'running' } },
        ],
      }))
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      fireEvent.click(screen.getByText('Livestream'))
      expect(screen.getByText('worker update')).toBeInTheDocument()
    })
  })

  describe('View Log link', () => {
    it('shows View Log link on each background worker card when onViewLog provided', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onViewLog={() => {}} />)
      for (const def of BACKGROUND_WORKERS) {
        expect(screen.getByTestId(`view-log-${def.key}`)).toBeInTheDocument()
        expect(screen.getByTestId(`view-log-${def.key}`)).toHaveTextContent('View Log')
      }
    })

    it('does not show View Log link when onViewLog is not provided', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      expect(screen.queryByText('View Log')).not.toBeInTheDocument()
    })

    it('clicking View Log calls onViewLog with bg-prefixed key', () => {
      const onViewLog = vi.fn()
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onViewLog={onViewLog} />)
      fireEvent.click(screen.getByTestId('view-log-memory_sync'))
      expect(onViewLog).toHaveBeenCalledWith('bg-memory_sync')
    })
  })
})

describe('formatInterval', () => {
  let formatInterval
  beforeEach(async () => {
    const mod = await import('../SystemPanel')
    formatInterval = mod.formatInterval
  })

  it('returns null for null input', () => {
    expect(formatInterval(null)).toBeNull()
  })

  it('returns null for undefined input', () => {
    expect(formatInterval(undefined)).toBeNull()
  })

  it('formats seconds under 60', () => {
    expect(formatInterval(30)).toBe('every 30s')
  })

  it('formats minutes under 60', () => {
    expect(formatInterval(300)).toBe('every 5m')
    expect(formatInterval(1800)).toBe('every 30m')
  })

  it('formats exact hours', () => {
    expect(formatInterval(3600)).toBe('every 1h')
    expect(formatInterval(7200)).toBe('every 2h')
  })

  it('formats hours with remaining minutes', () => {
    expect(formatInterval(5400)).toBe('every 1h 30m')
  })
})

describe('formatNextRun', () => {
  let formatNextRun
  beforeEach(async () => {
    const mod = await import('../SystemPanel')
    formatNextRun = mod.formatNextRun
  })

  it('returns null when lastRun is null', () => {
    expect(formatNextRun(null, 3600)).toBeNull()
  })

  it('returns null when intervalSeconds is null', () => {
    expect(formatNextRun('2026-02-20T10:00:00Z', null)).toBeNull()
  })

  it('returns "now" when next run is overdue', () => {
    const pastTime = new Date(Date.now() - 10000).toISOString()
    expect(formatNextRun(pastTime, 1)).toBe('now')
  })

  it('returns time remaining for future next run', () => {
    const recentTime = new Date(Date.now() - 1000).toISOString()
    const result = formatNextRun(recentTime, 7200)
    expect(result).toMatch(/^in \d+/)
  })
})

describe('BackgroundWorkerCard schedule display', () => {
  let SystemPanel
  beforeEach(async () => {
    const mod = await import('../SystemPanel')
    SystemPanel = mod.SystemPanel
  })

  it('shows schedule when interval_seconds is present', () => {
    const bgWorkers = [
      { name: 'memory_sync', status: 'ok', enabled: true, last_run: '2026-02-20T10:00:00Z', interval_seconds: 3600, details: {} },
    ]
    render(<SystemPanel workers={{}} backgroundWorkers={bgWorkers} />)
    expect(screen.getByTestId('schedule-memory_sync')).toBeInTheDocument()
    expect(screen.getByText(/Runs every 1h/)).toBeInTheDocument()
  })

  it('does not show schedule when interval_seconds is null', () => {
    const bgWorkers = [
      { name: 'retrospective', status: 'ok', enabled: true, last_run: null, details: {} },
    ]
    render(<SystemPanel workers={{}} backgroundWorkers={bgWorkers} />)
    expect(screen.queryByTestId('schedule-retrospective')).not.toBeInTheDocument()
  })

  it('shows edit link for editable workers', () => {
    const bgWorkers = [
      { name: 'memory_sync', status: 'ok', enabled: true, last_run: null, interval_seconds: 3600, details: {} },
    ]
    render(<SystemPanel workers={{}} backgroundWorkers={bgWorkers} onUpdateInterval={() => {}} />)
    expect(screen.getByTestId('edit-interval-memory_sync')).toBeInTheDocument()
  })

  it('shows interval editor when edit is clicked', () => {
    const bgWorkers = [
      { name: 'memory_sync', status: 'ok', enabled: true, last_run: null, interval_seconds: 3600, details: {} },
    ]
    render(<SystemPanel workers={{}} backgroundWorkers={bgWorkers} onUpdateInterval={() => {}} />)
    fireEvent.click(screen.getByTestId('edit-interval-memory_sync'))
    expect(screen.getByTestId('interval-editor-memory_sync')).toBeInTheDocument()
    expect(screen.getByTestId('preset-1h')).toBeInTheDocument()
    expect(screen.getByTestId('preset-2h')).toBeInTheDocument()
  })

  it('calls onUpdateInterval when preset is clicked', () => {
    const onUpdate = vi.fn()
    const bgWorkers = [
      { name: 'memory_sync', status: 'ok', enabled: true, last_run: null, interval_seconds: 3600, details: {} },
    ]
    render(<SystemPanel workers={{}} backgroundWorkers={bgWorkers} onUpdateInterval={onUpdate} />)
    fireEvent.click(screen.getByTestId('edit-interval-memory_sync'))
    fireEvent.click(screen.getByTestId('preset-2h'))
    expect(onUpdate).toHaveBeenCalledWith('memory_sync', 7200)
  })
})
