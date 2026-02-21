import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SystemPanel } from '../SystemPanel'

const mockBgWorkers = [
  { name: 'memory_sync', status: 'ok', last_run: new Date().toISOString(), details: { item_count: 12, digest_chars: 2400 } },
  { name: 'retrospective', status: 'error', last_run: '2026-02-20T10:28:00Z', details: { last_issue: 42 } },
  { name: 'metrics', status: 'ok', last_run: '2026-02-20T10:25:00Z', details: {} },
  { name: 'review_insights', status: 'disabled', last_run: null, details: {} },
]

const mockPipelineWorkers = {
  'triage-5': { status: 'evaluating', worker: 1, role: 'triage', title: 'Triage Issue #5', branch: '', transcript: ['Evaluating issue...', 'Checking labels'], pr: null },
  'plan-7': { status: 'planning', worker: 2, role: 'planner', title: 'Plan Issue #7', branch: '', transcript: ['Reading codebase...'], pr: null },
  10: { status: 'running', worker: 3, role: 'implementer', title: 'Issue #10', branch: 'agent/issue-10', transcript: ['Writing code...', 'Running tests...', 'All tests pass'], pr: null },
  'review-20': { status: 'reviewing', worker: 4, role: 'reviewer', title: 'PR #20 (Issue #3)', branch: '', transcript: [], pr: 20 },
}

describe('SystemPanel', () => {
  describe('Background Workers', () => {
    it('renders all 4 background worker cards', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      expect(screen.getByText('Memory Sync')).toBeInTheDocument()
      expect(screen.getByText('Retrospective')).toBeInTheDocument()
      // Use getAllByText since 'Metrics' label appears in both heading and worker card
      expect(screen.getAllByText('Metrics').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('Review Insights')).toBeInTheDocument()
    })

    it('shows correct status dot color for ok workers', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      const dot = screen.getByTestId('dot-memory_sync')
      expect(dot.style.background).toBe('var(--green)')
    })

    it('shows correct status dot color for error workers', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      const dot = screen.getByTestId('dot-retrospective')
      expect(dot.style.background).toBe('var(--red)')
    })

    it('shows correct status dot color for disabled workers', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      const dot = screen.getByTestId('dot-review_insights')
      expect(dot.style.background).toBe('var(--text-inactive)')
    })

    it('shows disabled state when worker has not reported', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      expect(screen.getByText('Memory Sync')).toBeInTheDocument()
      const dots = [
        screen.getByTestId('dot-memory_sync'),
        screen.getByTestId('dot-retrospective'),
        screen.getByTestId('dot-metrics'),
        screen.getByTestId('dot-review_insights'),
      ]
      dots.forEach(dot => {
        expect(dot.style.background).toBe('var(--text-inactive)')
      })
    })

    it('shows last run time when available', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      expect(screen.getAllByText(/Last run:/).length).toBe(4)
    })

    it('shows "never" for workers that have not run', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      const neverTexts = screen.getAllByText(/never/)
      expect(neverTexts.length).toBe(4)
    })

    it('shows detail key-value pairs', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      expect(screen.getByText('item count')).toBeInTheDocument()
      expect(screen.getByText('12')).toBeInTheDocument()
      expect(screen.getByText('digest chars')).toBeInTheDocument()
      expect(screen.getByText('2400')).toBeInTheDocument()
    })
  })

  describe('Pipeline Workers', () => {
    it('shows "No active pipeline workers" when no workers', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={[]} />)
      expect(screen.getByText('No active pipeline workers')).toBeInTheDocument()
    })

    it('renders pipeline worker cards', () => {
      render(<SystemPanel workers={mockPipelineWorkers} backgroundWorkers={[]} />)
      expect(screen.getByText('Pipeline Workers')).toBeInTheDocument()
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
      // Worker #10 has 3 transcript lines
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
      // review-20 has empty transcript
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

  describe('Background Worker Toggles', () => {
    it('shows On buttons when onToggleBgWorker is provided', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onToggleBgWorker={() => {}} />)
      const onButtons = screen.getAllByText('On')
      expect(onButtons.length).toBeGreaterThan(0)
    })

    it('does not show toggle buttons when onToggleBgWorker is not provided', () => {
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} />)
      expect(screen.queryByText('On')).not.toBeInTheDocument()
      expect(screen.queryByText('Off')).not.toBeInTheDocument()
    })

    it('calls onToggleBgWorker with correct worker key when toggled', () => {
      const onToggle = vi.fn()
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onToggleBgWorker={onToggle} />)
      const onButtons = screen.getAllByText('On')
      fireEvent.click(onButtons[0]) // First "On" button = memory_sync
      expect(onToggle).toHaveBeenCalledWith('memory_sync', false)
    })

    it('shows Off button for disabled workers', () => {
      const onToggle = vi.fn()
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onToggleBgWorker={onToggle} />)
      expect(screen.getByText('Off')).toBeInTheDocument()
    })

    it('clicking Off toggles to enabled', () => {
      const onToggle = vi.fn()
      render(<SystemPanel workers={{}} backgroundWorkers={mockBgWorkers} onToggleBgWorker={onToggle} />)
      fireEvent.click(screen.getByText('Off'))
      expect(onToggle).toHaveBeenCalledWith('review_insights', true)
    })
  })
})
