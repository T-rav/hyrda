import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PIPELINE_STAGES } from '../../constants'
import { deriveStageStatus } from '../../hooks/useStageStatus'
import { STAGE_KEYS } from '../../hooks/useTimeline'

const mockUseHydra = vi.fn()

vi.mock('../../context/HydraContext', () => ({
  useHydra: (...args) => mockUseHydra(...args),
}))

const { StreamView, toStreamIssue } = await import('../StreamView')

function defaultHydraContext(overrides = {}) {
  const defaultPipeline = { triage: [], plan: [], implement: [], review: [], merged: [] }
  const pipelineIssues = overrides.pipelineIssues
    ? { ...defaultPipeline, ...overrides.pipelineIssues }
    : defaultPipeline
  const workers = overrides.workers || {}
  const backgroundWorkers = overrides.backgroundWorkers || []
  return {
    pipelineIssues,
    workers,
    prs: [],
    backgroundWorkers,
    stageStatus: deriveStageStatus(pipelineIssues, workers, backgroundWorkers, {}),
    ...overrides,
  }
}

const defaultHydra = defaultHydraContext()

beforeEach(() => {
  mockUseHydra.mockReturnValue(defaultHydraContext())
})

// All stages open by default for test visibility
const allExpanded = Object.fromEntries(PIPELINE_STAGES.map(s => [s.key, true]))

const defaultProps = {
  intents: [],
  expandedStages: allExpanded,
  onToggleStage: () => {},
  onViewTranscript: () => {},
  onRequestChanges: () => {},
}

const basePipeIssue = {
  issue_number: 42,
  title: 'Test issue',
  url: 'https://github.com/test/42',
}

describe('StreamView stage indicators', () => {
  describe('Status dot colors', () => {
    it('shows green dot when stage has active workers', () => {
      mockUseHydra.mockReturnValue(defaultHydraContext({
        workers: {
          'triage-5': { status: 'evaluating', worker: 1, role: 'triage', title: 'Triage #5', branch: '', transcript: [], pr: null },
        },
        pipelineIssues: {
          triage: [{ issue_number: 5, title: 'Test', status: 'active' }],
          plan: [], implement: [], review: [],
        },
        backgroundWorkers: [
          { name: 'triage', status: 'ok', enabled: true, last_run: null, details: {} },
        ],
      }))
      render(<StreamView {...defaultProps} />)
      const dot = screen.getByTestId('stage-dot-triage')
      expect(dot.style.background).toBe('var(--green)')
    })

    it('shows yellow dot when stage is enabled but no active workers', () => {
      mockUseHydra.mockReturnValue(defaultHydraContext({
        backgroundWorkers: [
          { name: 'plan', status: 'ok', enabled: true, last_run: null, details: {} },
        ],
      }))
      render(<StreamView {...defaultProps} />)
      const dot = screen.getByTestId('stage-dot-plan')
      expect(dot.style.background).toBe('var(--yellow)')
    })

    it('shows red dot when stage is disabled', () => {
      mockUseHydra.mockReturnValue(defaultHydraContext({
        backgroundWorkers: [
          { name: 'implement', status: 'ok', enabled: false, last_run: null, details: {} },
        ],
      }))
      render(<StreamView {...defaultProps} />)
      const dot = screen.getByTestId('stage-dot-implement')
      expect(dot.style.background).toBe('var(--red)')
    })

    it('defaults to enabled (yellow) when no backgroundWorkers entry exists', () => {
      mockUseHydra.mockReturnValue(defaultHydraContext({
        backgroundWorkers: [],
      }))
      render(<StreamView {...defaultProps} />)
      const dot = screen.getByTestId('stage-dot-triage')
      expect(dot.style.background).toBe('var(--yellow)')
    })
  })

  describe('Disabled badge', () => {
    it('shows "Disabled" badge when stage is disabled', () => {
      mockUseHydra.mockReturnValue(defaultHydraContext({
        backgroundWorkers: [
          { name: 'review', status: 'ok', enabled: false, last_run: null, details: {} },
        ],
      }))
      render(<StreamView {...defaultProps} />)
      expect(screen.getByTestId('stage-disabled-review')).toHaveTextContent('Disabled')
    })

    it('does not show "Disabled" badge when stage is enabled', () => {
      mockUseHydra.mockReturnValue(defaultHydraContext({
        backgroundWorkers: [
          { name: 'review', status: 'ok', enabled: true, last_run: null, details: {} },
        ],
      }))
      render(<StreamView {...defaultProps} />)
      expect(screen.queryByTestId('stage-disabled-review')).not.toBeInTheDocument()
    })
  })

  describe('Opacity dimming', () => {
    it('applies reduced opacity when stage is disabled', () => {
      mockUseHydra.mockReturnValue(defaultHydraContext({
        backgroundWorkers: [
          { name: 'implement', status: 'ok', enabled: false, last_run: null, details: {} },
        ],
      }))
      render(<StreamView {...defaultProps} />)
      const section = screen.getByTestId('stage-section-implement')
      expect(section.style.opacity).toBe('0.5')
    })

    it('has full opacity when stage is enabled', () => {
      mockUseHydra.mockReturnValue(defaultHydraContext({
        backgroundWorkers: [
          { name: 'implement', status: 'ok', enabled: true, last_run: null, details: {} },
        ],
      }))
      render(<StreamView {...defaultProps} />)
      const section = screen.getByTestId('stage-section-implement')
      expect(section.style.opacity).toBe('1')
    })
  })

  describe('Merged stage exclusion', () => {
    it('does not render status dot for merged stage', () => {
      render(<StreamView {...defaultProps} />)
      expect(screen.queryByTestId('stage-dot-merged')).not.toBeInTheDocument()
    })
  })

  describe('Multiple stages with mixed states', () => {
    it('shows correct indicators for multiple stages simultaneously', () => {
      mockUseHydra.mockReturnValue(defaultHydraContext({
        workers: {
          'triage-5': { status: 'evaluating', worker: 1, role: 'triage', title: 'Triage #5', branch: '', transcript: [], pr: null },
        },
        backgroundWorkers: [
          { name: 'triage', status: 'ok', enabled: true, last_run: null, details: {} },
          { name: 'plan', status: 'ok', enabled: true, last_run: null, details: {} },
          { name: 'implement', status: 'ok', enabled: false, last_run: null, details: {} },
          { name: 'review', status: 'ok', enabled: true, last_run: null, details: {} },
        ],
      }))
      render(<StreamView {...defaultProps} />)
      // Triage: enabled + active worker = green
      expect(screen.getByTestId('stage-dot-triage').style.background).toBe('var(--green)')
      // Plan: enabled + no workers = yellow
      expect(screen.getByTestId('stage-dot-plan').style.background).toBe('var(--yellow)')
      // Implement: disabled = red
      expect(screen.getByTestId('stage-dot-implement').style.background).toBe('var(--red)')
      // Review: enabled + no workers = yellow
      expect(screen.getByTestId('stage-dot-review').style.background).toBe('var(--yellow)')

      // Only implement should be disabled
      expect(screen.getByTestId('stage-disabled-implement')).toBeInTheDocument()
      expect(screen.queryByTestId('stage-disabled-triage')).not.toBeInTheDocument()
      expect(screen.queryByTestId('stage-disabled-plan')).not.toBeInTheDocument()
      expect(screen.queryByTestId('stage-disabled-review')).not.toBeInTheDocument()

      // Opacity check
      expect(screen.getByTestId('stage-section-implement').style.opacity).toBe('0.5')
      expect(screen.getByTestId('stage-section-triage').style.opacity).toBe('1')
    })
  })
})

describe('toStreamIssue status mapping', () => {
  it('maps active status to overallStatus active', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'plan', [])
    expect(result.overallStatus).toBe('active')
  })

  it('maps queued status to overallStatus queued', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'queued' }, 'plan', [])
    expect(result.overallStatus).toBe('queued')
  })

  it('maps hitl status to overallStatus hitl', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'hitl' }, 'plan', [])
    expect(result.overallStatus).toBe('hitl')
  })

  it('maps failed status to overallStatus failed', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'failed' }, 'plan', [])
    expect(result.overallStatus).toBe('failed')
  })

  it('maps error status to overallStatus failed', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'error' }, 'plan', [])
    expect(result.overallStatus).toBe('failed')
  })

  it('maps done status to overallStatus done', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'done' }, 'merged', [])
    expect(result.overallStatus).toBe('done')
  })

  it('maps unknown status to overallStatus queued', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'something_else' }, 'plan', [])
    expect(result.overallStatus).toBe('queued')
  })

  it('defaults to queued when status is undefined', () => {
    const result = toStreamIssue({ ...basePipeIssue }, 'plan', [])
    expect(result.overallStatus).toBe('queued')
  })
})

describe('toStreamIssue stage building', () => {
  it('sets all stages to done for merged/done items', () => {
    const result = toStreamIssue(
      { issue_number: 10, title: 'Test', status: 'done' },
      'merged',
      []
    )
    for (const key of STAGE_KEYS) {
      expect(result.stages[key].status).toBe('done')
    }
    expect(result.overallStatus).toBe('done')
  })

  it('sets current stage to active when issue status is active', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'implement', [])
    expect(result.stages.triage.status).toBe('done')
    expect(result.stages.plan.status).toBe('done')
    expect(result.stages.implement.status).toBe('active')
    expect(result.stages.review.status).toBe('pending')
    expect(result.stages.merged.status).toBe('pending')
    expect(result.overallStatus).toBe('active')
  })

  it('sets current stage to queued when issue status is queued', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'queued' }, 'implement', [])
    expect(result.stages.triage.status).toBe('done')
    expect(result.stages.plan.status).toBe('done')
    expect(result.stages.implement.status).toBe('queued')
    expect(result.stages.review.status).toBe('pending')
    expect(result.stages.merged.status).toBe('pending')
    expect(result.overallStatus).toBe('queued')
  })

  it('sets current stage to failed for failed items', () => {
    const result = toStreamIssue(
      { issue_number: 10, title: 'Test', status: 'failed' },
      'implement',
      []
    )
    expect(result.overallStatus).toBe('failed')
    expect(result.stages.triage.status).toBe('done')
    expect(result.stages.plan.status).toBe('done')
    expect(result.stages.implement.status).toBe('failed')
    expect(result.stages.review.status).toBe('pending')
    expect(result.stages.merged.status).toBe('pending')
  })

  it('sets current stage to hitl for hitl items', () => {
    const result = toStreamIssue(
      { issue_number: 10, title: 'Test', status: 'hitl' },
      'review',
      []
    )
    expect(result.overallStatus).toBe('hitl')
    expect(result.stages.triage.status).toBe('done')
    expect(result.stages.plan.status).toBe('done')
    expect(result.stages.implement.status).toBe('done')
    expect(result.stages.review.status).toBe('hitl')
    expect(result.stages.merged.status).toBe('pending')
  })

  it('sets prior stages to done', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'review', [])
    expect(result.stages.triage.status).toBe('done')
    expect(result.stages.plan.status).toBe('done')
    expect(result.stages.implement.status).toBe('done')
  })

  it('sets later stages to pending', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'plan', [])
    expect(result.stages.implement.status).toBe('pending')
    expect(result.stages.review.status).toBe('pending')
    expect(result.stages.merged.status).toBe('pending')
  })
})

describe('toStreamIssue output shape', () => {
  it('returns correct issueNumber and title', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'plan', [])
    expect(result.issueNumber).toBe(42)
    expect(result.title).toBe('Test issue')
  })

  it('returns currentStage matching the stageKey argument', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'implement', [])
    expect(result.currentStage).toBe('implement')
  })

  it('builds a stages object with all STAGE_KEYS', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'plan', [])
    for (const key of STAGE_KEYS) {
      expect(result.stages).toHaveProperty(key)
      expect(result.stages[key]).toHaveProperty('status')
      expect(result.stages[key]).toHaveProperty('startTime')
      expect(result.stages[key]).toHaveProperty('endTime')
      expect(result.stages[key]).toHaveProperty('transcript')
    }
  })

  it('matches PR from prs array by issue_number', () => {
    const prs = [{ issue: 42, pr: 100, url: 'https://github.com/pr/100' }]
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'review', prs)
    expect(result.pr).toEqual({ number: 100, url: 'https://github.com/pr/100' })
  })

  it('returns null pr when no matching PR exists', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'plan', [])
    expect(result.pr).toBeNull()
  })
})

describe('Stage header failed/hitl counts', () => {
  it('shows failed count when stage has failed issues', () => {
    mockUseHydra.mockReturnValue(defaultHydraContext({
      pipelineIssues: {
        triage: [], plan: [], review: [],
        implement: [
          { issue_number: 1, title: 'Active issue', status: 'active' },
          { issue_number: 2, title: 'Failed issue', status: 'failed' },
        ],
      },
    }))
    render(<StreamView {...defaultProps} />)
    const section = screen.getByTestId('stage-section-implement')
    expect(section.textContent).toContain('1 failed')
  })

  it('shows hitl count when stage has hitl issues', () => {
    mockUseHydra.mockReturnValue(defaultHydraContext({
      pipelineIssues: {
        triage: [], plan: [], implement: [],
        review: [
          { issue_number: 1, title: 'Active issue', status: 'active' },
          { issue_number: 2, title: 'HITL issue', status: 'hitl' },
        ],
      },
    }))
    render(<StreamView {...defaultProps} />)
    const section = screen.getByTestId('stage-section-review')
    expect(section.textContent).toContain('1 hitl')
  })

  it('hides failed and hitl counts when zero', () => {
    mockUseHydra.mockReturnValue(defaultHydraContext({
      pipelineIssues: {
        triage: [], implement: [], review: [],
        plan: [
          { issue_number: 1, title: 'Active issue', status: 'active' },
          { issue_number: 2, title: 'Queued issue', status: 'queued' },
        ],
      },
    }))
    render(<StreamView {...defaultProps} />)
    const section = screen.getByTestId('stage-section-plan')
    expect(section.textContent).not.toContain('failed')
    expect(section.textContent).not.toContain('hitl')
  })

  it('excludes failed and hitl from queued count', () => {
    mockUseHydra.mockReturnValue(defaultHydraContext({
      pipelineIssues: {
        triage: [], plan: [], review: [],
        implement: [
          { issue_number: 1, title: 'Active', status: 'active' },
          { issue_number: 2, title: 'Failed', status: 'failed' },
          { issue_number: 3, title: 'HITL', status: 'hitl' },
        ],
      },
    }))
    render(<StreamView {...defaultProps} />)
    const section = screen.getByTestId('stage-section-implement')
    expect(section.textContent).toContain('1 active')
    expect(section.textContent).toContain('0 queued')
    expect(section.textContent).toContain('1 failed')
    expect(section.textContent).toContain('1 hitl')
  })

  it('shows correct counts with only failed issues (no active/queued)', () => {
    mockUseHydra.mockReturnValue(defaultHydraContext({
      pipelineIssues: {
        triage: [], plan: [], review: [],
        implement: [
          { issue_number: 1, title: 'Failed 1', status: 'failed' },
          { issue_number: 2, title: 'Failed 2', status: 'failed' },
        ],
      },
    }))
    render(<StreamView {...defaultProps} />)
    const section = screen.getByTestId('stage-section-implement')
    expect(section.textContent).toContain('0 active')
    expect(section.textContent).toContain('0 queued')
    expect(section.textContent).toContain('2 failed')
  })
})

describe('PipelineFlow visualization', () => {
  it('renders all pipeline stage labels in the flow', () => {
    mockUseHydra.mockReturnValue(defaultHydraContext({
      pipelineIssues: {
        triage: [{ issue_number: 1, title: 'Test', status: 'queued' }],
        plan: [], implement: [], review: [],
      },
    }))
    render(<StreamView {...defaultProps} />)
    const flow = screen.getByTestId('pipeline-flow')
    expect(flow).toBeInTheDocument()
    expect(flow.textContent).toContain('Triage')
    expect(flow.textContent).toContain('Plan')
    expect(flow.textContent).toContain('Implement')
    expect(flow.textContent).toContain('Review')
    expect(flow.textContent).toContain('Merged')
  })

  it('renders dots for issues at their current stage', () => {
    mockUseHydra.mockReturnValue(defaultHydraContext({
      pipelineIssues: {
        triage: [],
        plan: [
          { issue_number: 10, title: 'Plan issue', status: 'queued' },
          { issue_number: 11, title: 'Plan issue 2', status: 'active' },
        ],
        implement: [],
        review: [{ issue_number: 20, title: 'Review issue', status: 'active' }],
      },
    }))
    render(<StreamView {...defaultProps} />)
    expect(screen.getByTestId('flow-dot-10')).toBeInTheDocument()
    expect(screen.getByTestId('flow-dot-11')).toBeInTheDocument()
    expect(screen.getByTestId('flow-dot-20')).toBeInTheDocument()
  })

  it('does not render pipeline flow when no issues exist', () => {
    mockUseHydra.mockReturnValue(defaultHydraContext({
      pipelineIssues: { triage: [], plan: [], implement: [], review: [] },
    }))
    render(<StreamView {...defaultProps} />)
    expect(screen.queryByTestId('pipeline-flow')).not.toBeInTheDocument()
  })

  it('shows all stage labels even when some stages have no issues', () => {
    mockUseHydra.mockReturnValue(defaultHydraContext({
      pipelineIssues: {
        triage: [],
        plan: [{ issue_number: 5, title: 'Only plan', status: 'queued' }],
        implement: [], review: [],
      },
    }))
    render(<StreamView {...defaultProps} />)
    const flow = screen.getByTestId('pipeline-flow')
    expect(flow.textContent).toContain('Triage')
    expect(flow.textContent).toContain('Plan')
    expect(flow.textContent).toContain('Implement')
    expect(flow.textContent).toContain('Review')
    expect(flow.textContent).toContain('Merged')
  })

  it('applies pulse animation to active issue dots', () => {
    mockUseHydra.mockReturnValue(defaultHydraContext({
      pipelineIssues: {
        triage: [],
        plan: [
          { issue_number: 10, title: 'Active', status: 'active' },
          { issue_number: 11, title: 'Queued', status: 'queued' },
        ],
        implement: [], review: [],
      },
    }))
    render(<StreamView {...defaultProps} />)
    const activeDot = screen.getByTestId('flow-dot-10')
    const queuedDot = screen.getByTestId('flow-dot-11')
    expect(activeDot.style.animation).toContain('stream-pulse')
    expect(queuedDot.style.animation).toBe('')
  })
})

describe('Merged stage rendering', () => {
  it('renders merged PR issues in the merged stage section', () => {
    mockUseHydra.mockReturnValue(defaultHydraContext({
      prs: [{ pr: 42, issue: 10, title: 'Fix bug', merged: true, url: 'https://github.com/test/pr/42' }],
    }))
    render(<StreamView {...defaultProps} />)
    expect(screen.getByText('#10')).toBeInTheDocument()
    expect(screen.getByText('Fix bug')).toBeInTheDocument()
  })

  it('renders merged PR issue as a dot in PipelineFlow', () => {
    mockUseHydra.mockReturnValue(defaultHydraContext({
      prs: [{ pr: 42, issue: 10, title: 'Fix bug', merged: true, url: 'https://github.com/test/pr/42' }],
    }))
    render(<StreamView {...defaultProps} />)
    expect(screen.getByTestId('pipeline-flow')).toBeInTheDocument()
    const dot = screen.getByTestId('flow-dot-10')
    expect(dot).toBeInTheDocument()
    expect(dot.style.animation).toBe('')
  })
})

describe('PipelineFlow failed and hitl dots', () => {
  it('renders failed and hitl issue dots as non-pulsing', () => {
    mockUseHydra.mockReturnValue(defaultHydraContext({
      pipelineIssues: {
        triage: [],
        plan: [],
        implement: [
          { issue_number: 1, title: 'Failed issue', status: 'failed' },
          { issue_number: 2, title: 'HITL issue', status: 'hitl' },
        ],
        review: [],
      },
    }))
    render(<StreamView {...defaultProps} />)
    expect(screen.getByTestId('flow-dot-1')).toBeInTheDocument()
    expect(screen.getByTestId('flow-dot-2')).toBeInTheDocument()
    expect(screen.getByTestId('flow-dot-1').style.animation).toBe('')
    expect(screen.getByTestId('flow-dot-2').style.animation).toBe('')
  })
})
