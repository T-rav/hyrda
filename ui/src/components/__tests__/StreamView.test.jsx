import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PIPELINE_STAGES } from '../../constants'
import { STAGE_KEYS } from '../../hooks/useTimeline'

const mockUseHydra = vi.fn()

vi.mock('../../context/HydraContext', () => ({
  useHydra: (...args) => mockUseHydra(...args),
}))

const { StreamView, toStreamIssue } = await import('../StreamView')

const defaultHydra = {
  pipelineIssues: { triage: [], plan: [], implement: [], review: [] },
  workers: {},
  prs: [],
  backgroundWorkers: [],
}

beforeEach(() => {
  mockUseHydra.mockReturnValue(defaultHydra)
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

describe('StreamView stage indicators', () => {
  describe('Status dot colors', () => {
    it('shows green dot when stage has active workers', () => {
      mockUseHydra.mockReturnValue({
        ...defaultHydra,
        workers: {
          'triage-5': { status: 'evaluating', worker: 1, role: 'triage', title: 'Triage #5', branch: '', transcript: [], pr: null },
        },
        pipelineIssues: {
          ...defaultHydra.pipelineIssues,
          triage: [{ issue_number: 5, title: 'Test', status: 'active' }],
        },
        backgroundWorkers: [
          { name: 'triage', status: 'ok', enabled: true, last_run: null, details: {} },
        ],
      })
      render(<StreamView {...defaultProps} />)
      const dot = screen.getByTestId('stage-dot-triage')
      expect(dot.style.background).toBe('var(--green)')
    })

    it('shows yellow dot when stage is enabled but no active workers', () => {
      mockUseHydra.mockReturnValue({
        ...defaultHydra,
        backgroundWorkers: [
          { name: 'plan', status: 'ok', enabled: true, last_run: null, details: {} },
        ],
      })
      render(<StreamView {...defaultProps} />)
      const dot = screen.getByTestId('stage-dot-plan')
      expect(dot.style.background).toBe('var(--yellow)')
    })

    it('shows red dot when stage is disabled', () => {
      mockUseHydra.mockReturnValue({
        ...defaultHydra,
        backgroundWorkers: [
          { name: 'implement', status: 'ok', enabled: false, last_run: null, details: {} },
        ],
      })
      render(<StreamView {...defaultProps} />)
      const dot = screen.getByTestId('stage-dot-implement')
      expect(dot.style.background).toBe('var(--red)')
    })

    it('defaults to enabled (yellow) when no backgroundWorkers entry exists', () => {
      mockUseHydra.mockReturnValue({
        ...defaultHydra,
        backgroundWorkers: [],
      })
      render(<StreamView {...defaultProps} />)
      const dot = screen.getByTestId('stage-dot-triage')
      expect(dot.style.background).toBe('var(--yellow)')
    })
  })

  describe('Disabled badge', () => {
    it('shows "Disabled" badge when stage is disabled', () => {
      mockUseHydra.mockReturnValue({
        ...defaultHydra,
        backgroundWorkers: [
          { name: 'review', status: 'ok', enabled: false, last_run: null, details: {} },
        ],
      })
      render(<StreamView {...defaultProps} />)
      expect(screen.getByTestId('stage-disabled-review')).toHaveTextContent('Disabled')
    })

    it('does not show "Disabled" badge when stage is enabled', () => {
      mockUseHydra.mockReturnValue({
        ...defaultHydra,
        backgroundWorkers: [
          { name: 'review', status: 'ok', enabled: true, last_run: null, details: {} },
        ],
      })
      render(<StreamView {...defaultProps} />)
      expect(screen.queryByTestId('stage-disabled-review')).not.toBeInTheDocument()
    })
  })

  describe('Opacity dimming', () => {
    it('applies reduced opacity when stage is disabled', () => {
      mockUseHydra.mockReturnValue({
        ...defaultHydra,
        backgroundWorkers: [
          { name: 'implement', status: 'ok', enabled: false, last_run: null, details: {} },
        ],
      })
      render(<StreamView {...defaultProps} />)
      const section = screen.getByTestId('stage-section-implement')
      expect(section.style.opacity).toBe('0.5')
    })

    it('has full opacity when stage is enabled', () => {
      mockUseHydra.mockReturnValue({
        ...defaultHydra,
        backgroundWorkers: [
          { name: 'implement', status: 'ok', enabled: true, last_run: null, details: {} },
        ],
      })
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
      mockUseHydra.mockReturnValue({
        ...defaultHydra,
        workers: {
          'triage-5': { status: 'evaluating', worker: 1, role: 'triage', title: 'Triage #5', branch: '', transcript: [], pr: null },
        },
        backgroundWorkers: [
          { name: 'triage', status: 'ok', enabled: true, last_run: null, details: {} },
          { name: 'plan', status: 'ok', enabled: true, last_run: null, details: {} },
          { name: 'implement', status: 'ok', enabled: false, last_run: null, details: {} },
          { name: 'review', status: 'ok', enabled: true, last_run: null, details: {} },
        ],
      })
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

describe('toStreamIssue', () => {
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

  it('sets current stage to active for active items', () => {
    const result = toStreamIssue(
      { issue_number: 10, title: 'Test', status: 'active' },
      'implement',
      []
    )
    expect(result.stages.triage.status).toBe('done')
    expect(result.stages.plan.status).toBe('done')
    expect(result.stages.implement.status).toBe('active')
    expect(result.stages.review.status).toBe('pending')
    expect(result.stages.merged.status).toBe('pending')
    expect(result.overallStatus).toBe('active')
  })

  it('sets current stage to pending for queued items', () => {
    const result = toStreamIssue(
      { issue_number: 10, title: 'Test', status: 'queued' },
      'plan',
      []
    )
    expect(result.stages.triage.status).toBe('done')
    expect(result.stages.plan.status).toBe('pending')
    expect(result.stages.implement.status).toBe('pending')
    expect(result.stages.review.status).toBe('pending')
    expect(result.stages.merged.status).toBe('pending')
    expect(result.overallStatus).toBe('active')
  })

  it('sets overallStatus to hitl for hitl items', () => {
    const result = toStreamIssue(
      { issue_number: 10, title: 'Test', status: 'hitl' },
      'review',
      []
    )
    expect(result.overallStatus).toBe('hitl')
  })

  it('matches PR from prs array', () => {
    const result = toStreamIssue(
      { issue_number: 10, title: 'Test', status: 'active' },
      'review',
      [{ pr: 42, issue: 10, url: 'https://github.com/test/pr/42' }]
    )
    expect(result.pr).toEqual({ number: 42, url: 'https://github.com/test/pr/42' })
  })

  it('returns null pr when no match found', () => {
    const result = toStreamIssue(
      { issue_number: 10, title: 'Test', status: 'active' },
      'implement',
      [{ pr: 42, issue: 99, url: 'https://github.com/test/pr/42' }]
    )
    expect(result.pr).toBeNull()
  })
})

describe('Merged stage rendering', () => {
  it('renders merged PR issues in the merged stage section', () => {
    mockUseHydra.mockReturnValue({
      ...defaultHydra,
      prs: [{ pr: 42, issue: 10, title: 'Fix bug', merged: true, url: 'https://github.com/test/pr/42' }],
    })
    render(<StreamView {...defaultProps} />)
    expect(screen.getByText('#10')).toBeInTheDocument()
    expect(screen.getByText('Fix bug')).toBeInTheDocument()
  })
})
