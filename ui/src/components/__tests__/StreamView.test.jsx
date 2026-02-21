import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PIPELINE_STAGES } from '../../constants'

const mockUseHydra = vi.fn()

vi.mock('../../context/HydraContext', () => ({
  useHydra: (...args) => mockUseHydra(...args),
}))

const { StreamView } = await import('../StreamView')

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
      render(
        <StreamView
          intents={[]}
          expandedStages={allExpanded}
          onToggleStage={() => {}}
          onViewTranscript={() => {}}
          onRequestChanges={() => {}}
        />
      )
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
      render(
        <StreamView
          intents={[]}
          expandedStages={allExpanded}
          onToggleStage={() => {}}
          onViewTranscript={() => {}}
          onRequestChanges={() => {}}
        />
      )
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
      render(
        <StreamView
          intents={[]}
          expandedStages={allExpanded}
          onToggleStage={() => {}}
          onViewTranscript={() => {}}
          onRequestChanges={() => {}}
        />
      )
      const dot = screen.getByTestId('stage-dot-implement')
      expect(dot.style.background).toBe('var(--red)')
    })

    it('defaults to enabled (yellow) when no backgroundWorkers entry exists', () => {
      mockUseHydra.mockReturnValue({
        ...defaultHydra,
        backgroundWorkers: [],
      })
      render(
        <StreamView
          intents={[]}
          expandedStages={allExpanded}
          onToggleStage={() => {}}
          onViewTranscript={() => {}}
          onRequestChanges={() => {}}
        />
      )
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
      render(
        <StreamView
          intents={[]}
          expandedStages={allExpanded}
          onToggleStage={() => {}}
          onViewTranscript={() => {}}
          onRequestChanges={() => {}}
        />
      )
      expect(screen.getByTestId('stage-disabled-review')).toHaveTextContent('Disabled')
    })

    it('does not show "Disabled" badge when stage is enabled', () => {
      mockUseHydra.mockReturnValue({
        ...defaultHydra,
        backgroundWorkers: [
          { name: 'review', status: 'ok', enabled: true, last_run: null, details: {} },
        ],
      })
      render(
        <StreamView
          intents={[]}
          expandedStages={allExpanded}
          onToggleStage={() => {}}
          onViewTranscript={() => {}}
          onRequestChanges={() => {}}
        />
      )
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
      render(
        <StreamView
          intents={[]}
          expandedStages={allExpanded}
          onToggleStage={() => {}}
          onViewTranscript={() => {}}
          onRequestChanges={() => {}}
        />
      )
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
      render(
        <StreamView
          intents={[]}
          expandedStages={allExpanded}
          onToggleStage={() => {}}
          onViewTranscript={() => {}}
          onRequestChanges={() => {}}
        />
      )
      const section = screen.getByTestId('stage-section-implement')
      expect(section.style.opacity).toBe('1')
    })
  })

  describe('Worker count display', () => {
    it('shows worker count when active workers exist', () => {
      mockUseHydra.mockReturnValue({
        ...defaultHydra,
        workers: {
          10: { status: 'running', worker: 1, role: 'implementer', title: 'Issue #10', branch: '', transcript: [], pr: null },
          11: { status: 'testing', worker: 2, role: 'implementer', title: 'Issue #11', branch: '', transcript: [], pr: null },
        },
        backgroundWorkers: [
          { name: 'implement', status: 'ok', enabled: true, last_run: null, details: {} },
        ],
      })
      render(
        <StreamView
          intents={[]}
          expandedStages={allExpanded}
          onToggleStage={() => {}}
          onViewTranscript={() => {}}
          onRequestChanges={() => {}}
        />
      )
      const count = screen.getByTestId('stage-workers-implement')
      expect(count).toHaveTextContent('2')
    })

    it('hides worker count when zero active workers', () => {
      mockUseHydra.mockReturnValue({
        ...defaultHydra,
        backgroundWorkers: [
          { name: 'plan', status: 'ok', enabled: true, last_run: null, details: {} },
        ],
      })
      render(
        <StreamView
          intents={[]}
          expandedStages={allExpanded}
          onToggleStage={() => {}}
          onViewTranscript={() => {}}
          onRequestChanges={() => {}}
        />
      )
      expect(screen.queryByTestId('stage-workers-plan')).not.toBeInTheDocument()
    })
  })

  describe('Merged stage exclusion', () => {
    it('does not render status dot for merged stage', () => {
      render(
        <StreamView
          intents={[]}
          expandedStages={allExpanded}
          onToggleStage={() => {}}
          onViewTranscript={() => {}}
          onRequestChanges={() => {}}
        />
      )
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
      render(
        <StreamView
          intents={[]}
          expandedStages={allExpanded}
          onToggleStage={() => {}}
          onViewTranscript={() => {}}
          onRequestChanges={() => {}}
        />
      )
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
