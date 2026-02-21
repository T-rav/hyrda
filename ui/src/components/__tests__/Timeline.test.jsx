import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import {
  Timeline,
  stageFilterStyles,
  statusFilterStyles,
  statusIndicatorStyles,
  stageBadgeStyles,
  stageNodeStyles,
  stageConnectorStyles,
  issueCardBadgeStyles,
} from '../Timeline'
import { theme } from '../../theme'
import { STAGE_KEYS, STAGE_META } from '../../hooks/useTimeline'

// ── Pre-computed style tests ─────────────────────────────────────────

describe('Timeline pre-computed styles', () => {
  it('stageFilterStyles has active/inactive for each stage', () => {
    for (const key of STAGE_KEYS) {
      expect(stageFilterStyles[key]).toHaveProperty('active')
      expect(stageFilterStyles[key]).toHaveProperty('inactive')
      expect(stageFilterStyles[key].active.color).toBe(STAGE_META[key].color)
    }
  })

  it('statusFilterStyles has active variant for each status', () => {
    for (const key of ['all', 'active', 'done', 'failed', 'hitl']) {
      expect(statusFilterStyles[key]).toHaveProperty('active')
    }
  })

  it('statusIndicatorStyles has all status variants', () => {
    expect(statusIndicatorStyles.active).toHaveProperty('animation')
    expect(statusIndicatorStyles.done.color).toBe(theme.green)
    expect(statusIndicatorStyles.failed.color).toBe(theme.red)
    expect(statusIndicatorStyles.hitl.color).toBe(theme.yellow)
    expect(statusIndicatorStyles.pending).toHaveProperty('background')
  })

  it('stageBadgeStyles has variants for each status', () => {
    expect(stageBadgeStyles.active.color).toBe(theme.accent)
    expect(stageBadgeStyles.done.color).toBe(theme.green)
    expect(stageBadgeStyles.failed.color).toBe(theme.red)
    expect(stageBadgeStyles.hitl.color).toBe(theme.yellow)
    expect(stageBadgeStyles.pending.color).toBe(theme.textMuted)
  })

  it('stageNodeStyles has per-stage per-status dot variants', () => {
    for (const key of STAGE_KEYS) {
      expect(stageNodeStyles[key]).toHaveProperty('active')
      expect(stageNodeStyles[key]).toHaveProperty('done')
      expect(stageNodeStyles[key]).toHaveProperty('failed')
      expect(stageNodeStyles[key]).toHaveProperty('hitl')
      expect(stageNodeStyles[key]).toHaveProperty('pending')
      // Active/done nodes use stage color
      expect(stageNodeStyles[key].done.background).toBe(STAGE_META[key].color)
      // Failed nodes use red
      expect(stageNodeStyles[key].failed.background).toBe(theme.red)
      // Pending nodes are transparent
      expect(stageNodeStyles[key].pending.background).toBe('transparent')
    }
  })

  it('stageConnectorStyles has active/pending for each stage', () => {
    for (const key of STAGE_KEYS) {
      expect(stageConnectorStyles[key]).toHaveProperty('active')
      expect(stageConnectorStyles[key]).toHaveProperty('pending')
      expect(stageConnectorStyles[key].active.background).toBe(STAGE_META[key].color)
    }
  })

  it('issueCardBadgeStyles has variant for each pipeline stage', () => {
    for (const key of STAGE_KEYS) {
      expect(issueCardBadgeStyles[key]).toHaveProperty('background')
      expect(issueCardBadgeStyles[key].color).toBe(STAGE_META[key].color)
    }
  })
})

// ── Component rendering tests ────────────────────────────────────────

describe('Timeline component', () => {
  it('renders empty state when no events or workers', () => {
    render(<Timeline events={[]} workers={{}} prs={[]} />)
    expect(screen.getByText('No issues processed yet')).toBeInTheDocument()
  })

  it('renders issue count in filter bar', () => {
    render(<Timeline events={[]} workers={{}} prs={[]} />)
    expect(screen.getByText('0 issues')).toBeInTheDocument()
  })

  it('renders issue cards from events', () => {
    const events = [
      { type: 'triage_update', timestamp: '2026-01-15T10:00:00Z', data: { issue: 42, status: 'running' } },
      { type: 'triage_update', timestamp: '2026-01-15T10:01:00Z', data: { issue: 10, status: 'done' } },
    ]
    render(<Timeline events={events} workers={{}} prs={[]} />)

    expect(screen.getByText('#42')).toBeInTheDocument()
    expect(screen.getByText('#10')).toBeInTheDocument()
    expect(screen.getByText('2 issues')).toBeInTheDocument()
  })

  it('renders issue cards from workers state', () => {
    const workers = {
      5: { status: 'running', role: 'implementer', title: 'Issue #5', branch: 'agent/issue-5', transcript: [], pr: null },
    }
    render(<Timeline events={[]} workers={workers} prs={[]} />)

    expect(screen.getByText('#5')).toBeInTheDocument()
    expect(screen.getByText('1 issue')).toBeInTheDocument()
  })

  it('shows stage badge on issue card with correct label', () => {
    const events = [
      { type: 'worker_update', timestamp: '2026-01-15T10:00:00Z', data: { issue: 7, status: 'running' } },
    ]
    render(<Timeline events={events} workers={{}} prs={[]} />)

    // "Implement" appears both in filter bar and issue card badge — verify at least 2
    const matches = screen.getAllByText('Implement')
    expect(matches.length).toBeGreaterThanOrEqual(2)
  })

  it('shows status indicator for active issues', () => {
    const workers = {
      3: { status: 'running', role: 'implementer', title: 'Issue #3', branch: '', transcript: [], pr: null },
    }
    render(<Timeline events={[]} workers={workers} prs={[]} />)

    expect(screen.getByTestId('status-active')).toBeInTheDocument()
  })

  it('shows checkmark for done issues', () => {
    const events = [
      { type: 'worker_update', timestamp: '2026-01-15T10:00:00Z', data: { issue: 7, status: 'done' } },
      { type: 'merge_update', timestamp: '2026-01-15T10:01:00Z', data: { issue: 7, pr: 20, status: 'merged' } },
    ]
    render(<Timeline events={events} workers={{}} prs={[]} />)

    expect(screen.getByText('✓')).toBeInTheDocument()
  })

  it('shows X for failed issues', () => {
    const events = [
      { type: 'worker_update', timestamp: '2026-01-15T10:00:00Z', data: { issue: 7, status: 'failed' } },
    ]
    render(<Timeline events={events} workers={{}} prs={[]} />)

    expect(screen.getByText('✗')).toBeInTheDocument()
  })

  it('shows warning for HITL issues', () => {
    const events = [
      { type: 'review_update', timestamp: '2026-01-15T10:00:00Z', data: { issue: 7, pr: 10, status: 'escalated' } },
    ]
    render(<Timeline events={events} workers={{}} prs={[]} />)

    expect(screen.getByText('⚠')).toBeInTheDocument()
  })

  it('clicking issue card toggles expanded timeline', () => {
    const events = [
      { type: 'triage_update', timestamp: '2026-01-15T10:00:00Z', data: { issue: 42, status: 'done' } },
    ]
    render(<Timeline events={events} workers={{}} prs={[]} />)

    // Timeline should not be visible initially
    expect(screen.queryByTestId('timeline-42')).not.toBeInTheDocument()

    // Click to expand
    fireEvent.click(screen.getByText('#42'))
    expect(screen.getByTestId('timeline-42')).toBeInTheDocument()

    // Click again to collapse
    fireEvent.click(screen.getByText('#42'))
    expect(screen.queryByTestId('timeline-42')).not.toBeInTheDocument()
  })

  it('expanded timeline shows all 5 stage nodes', () => {
    const events = [
      { type: 'triage_update', timestamp: '2026-01-15T10:00:00Z', data: { issue: 1, status: 'done' } },
    ]
    render(<Timeline events={events} workers={{}} prs={[]} />)

    // Expand the issue card
    fireEvent.click(screen.getByText('#1'))

    // Stage labels appear in both filter bar and expanded timeline
    // Verify that expanding adds the timeline node (at least 2 = filter + timeline node)
    expect(screen.getByTestId('timeline-1')).toBeInTheDocument()
    expect(screen.getAllByText('Triage').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText('Plan').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText('Implement').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText('Review').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText('Merged').length).toBeGreaterThanOrEqual(2)
  })

  it('shows transcript preview when stage has transcript lines', () => {
    const events = [
      { type: 'triage_update', timestamp: '2026-01-15T10:00:00Z', data: { issue: 5, status: 'running' } },
      { type: 'transcript_line', timestamp: '2026-01-15T10:01:00Z', data: { issue: 5, source: 'triage', line: 'Analyzing issue context...' } },
    ]
    render(<Timeline events={events} workers={{}} prs={[]} />)

    // Expand the issue card
    fireEvent.click(screen.getByText('#5'))
    expect(screen.getByText('Analyzing issue context...')).toBeInTheDocument()
  })

  it('transcript toggle shows/hides additional lines', () => {
    // Events are stored newest-first (per useHydraSocket convention)
    const events = []
    for (let i = 7; i >= 0; i--) {
      events.push({
        type: 'transcript_line',
        timestamp: `2026-01-15T10:0${i + 1}:00Z`,
        data: { issue: 5, source: 'triage', line: `triage-line-${i}` },
      })
    }
    events.push(
      { type: 'triage_update', timestamp: '2026-01-15T10:00:00Z', data: { issue: 5, status: 'running' } },
    )

    render(<Timeline events={events} workers={{}} prs={[]} />)
    fireEvent.click(screen.getByText('#5'))

    // Only last 5 lines visible by default (lines 3-7)
    expect(screen.getByText('triage-line-3')).toBeInTheDocument()
    expect(screen.getByText('triage-line-7')).toBeInTheDocument()
    expect(screen.queryByText('triage-line-0')).not.toBeInTheDocument()

    // Toggle shows all
    fireEvent.click(screen.getByText('Show all 8 lines'))
    expect(screen.getByText('triage-line-0')).toBeInTheDocument()
    expect(screen.getByText('Show less')).toBeInTheDocument()

    // Toggle back
    fireEvent.click(screen.getByText('Show less'))
    expect(screen.queryByText('triage-line-0')).not.toBeInTheDocument()
  })

  it('shows PR link in review stage when PR exists', () => {
    const events = [
      { type: 'worker_update', timestamp: '2026-01-15T10:00:00Z', data: { issue: 3, status: 'done' } },
      { type: 'pr_created', timestamp: '2026-01-15T10:01:00Z', data: { issue: 3, pr: 25 } },
      { type: 'review_update', timestamp: '2026-01-15T10:02:00Z', data: { issue: 3, pr: 25, status: 'reviewing' } },
    ]
    render(<Timeline events={events} workers={{}} prs={[]} />)

    fireEvent.click(screen.getByText('#3'))
    expect(screen.getByText('PR #25')).toBeInTheDocument()
  })

  it('shows branch in implement stage', () => {
    const workers = {
      42: { status: 'running', role: 'implementer', title: 'Issue #42', branch: 'agent/issue-42', transcript: [], pr: null },
    }
    render(<Timeline events={[]} workers={workers} prs={[]} />)

    fireEvent.click(screen.getByText('#42'))
    expect(screen.getByText('agent/issue-42')).toBeInTheDocument()
  })
})

// ── Filter/sort interaction tests ────────────────────────────────────

describe('Timeline filter and sort', () => {
  const events = [
    { type: 'triage_update', timestamp: '2026-01-15T10:00:00Z', data: { issue: 1, status: 'running' } },
    { type: 'worker_update', timestamp: '2026-01-15T10:01:00Z', data: { issue: 2, status: 'running' } },
    { type: 'worker_update', timestamp: '2026-01-15T10:02:00Z', data: { issue: 3, status: 'failed' } },
  ]

  it('stage filter filters issue list', () => {
    render(<Timeline events={events} workers={{}} prs={[]} />)

    expect(screen.getByText('3 issues')).toBeInTheDocument()

    // Click the "Triage" filter pill (it's in the filter bar — first occurrence)
    const triagePills = screen.getAllByText('Triage')
    fireEvent.click(triagePills[0])
    expect(screen.getByText('1 issue')).toBeInTheDocument()
    expect(screen.getByText('#1')).toBeInTheDocument()
    expect(screen.queryByText('#2')).not.toBeInTheDocument()
  })

  it('status filter filters issue list', () => {
    render(<Timeline events={events} workers={{}} prs={[]} />)

    // Click the "Failed" status filter
    fireEvent.click(screen.getByText('Failed'))
    expect(screen.getByText('1 issue')).toBeInTheDocument()
    expect(screen.getByText('#3')).toBeInTheDocument()
  })

  it('sort toggle changes order', () => {
    render(<Timeline events={events} workers={{}} prs={[]} />)

    // Click "Issue #" sort
    fireEvent.click(screen.getByText('Issue #'))

    // Issues should be sorted by issue number descending
    // Query issue number spans — they are exact matches for "#N" pattern
    const issueCards = screen.getAllByText(/^#\d+$/)
    const nums = issueCards.map(el => el.textContent)
    expect(nums).toEqual(['#3', '#2', '#1'])
  })

  it('clicking "All" stage filter resets stage filter', () => {
    render(<Timeline events={events} workers={{}} prs={[]} />)

    // Apply filter — click first "Triage" (filter bar pill)
    const triagePills = screen.getAllByText('Triage')
    fireEvent.click(triagePills[0])
    expect(screen.getByText('1 issue')).toBeInTheDocument()

    // Reset with All — click the first "All" which is the stage filter
    const allButtons = screen.getAllByText('All')
    fireEvent.click(allButtons[0])
    expect(screen.getByText('3 issues')).toBeInTheDocument()
  })
})
