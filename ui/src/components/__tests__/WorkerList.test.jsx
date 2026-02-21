import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { WorkerList, cardStyle, cardActiveStyle, statusBadgeStyles, sectionHeaderStyles, sectionLabelStyles, sectionCountStyles } from '../WorkerList'
import { PIPELINE_STAGES } from '../../constants'

const statusColors = {
  queued:              { bg: 'var(--muted-subtle)',  fg: 'var(--text-muted)' },
  running:             { bg: 'var(--accent-subtle)', fg: 'var(--accent)' },
  planning:            { bg: 'var(--purple-subtle)', fg: 'var(--purple)' },
  testing:             { bg: 'var(--yellow-subtle)', fg: 'var(--yellow)' },
  committing:          { bg: 'var(--orange-subtle)', fg: 'var(--orange)' },
  quality_fix:         { bg: 'var(--yellow-subtle)', fg: 'var(--yellow)' },
  merge_fix:           { bg: 'var(--orange-subtle)', fg: 'var(--orange)' },
  reviewing:           { bg: 'var(--orange-subtle)', fg: 'var(--orange)' },
  start:               { bg: 'var(--orange-subtle)', fg: 'var(--orange)' },
  merge_main:          { bg: 'var(--accent-subtle)', fg: 'var(--accent)' },
  ci_wait:             { bg: 'var(--purple-subtle)', fg: 'var(--purple)' },
  ci_fix:              { bg: 'var(--yellow-subtle)', fg: 'var(--yellow)' },
  merging:             { bg: 'var(--green-subtle)',  fg: 'var(--green)' },
  escalating:          { bg: 'var(--red-subtle)',    fg: 'var(--red)' },
  escalated:           { bg: 'var(--red-subtle)',    fg: 'var(--red)' },
  evaluating:          { bg: 'var(--green-subtle)',  fg: 'var(--triage-green)' },
  validating:          { bg: 'var(--purple-subtle)', fg: 'var(--purple)' },
  retrying:            { bg: 'var(--yellow-subtle)', fg: 'var(--yellow)' },
  fixing:              { bg: 'var(--orange-subtle)', fg: 'var(--orange)' },
  fix_done:            { bg: 'var(--green-subtle)',  fg: 'var(--green)' },
  done:                { bg: 'var(--green-subtle)',  fg: 'var(--green)' },
  failed:              { bg: 'var(--red-subtle)',    fg: 'var(--red)' },
}

describe('WorkerList pre-computed styles', () => {
  it('cardActiveStyle includes properties from both card and active', () => {
    // card props
    expect(cardActiveStyle).toHaveProperty('padding')
    expect(cardActiveStyle).toHaveProperty('cursor', 'pointer')
    // active props
    expect(cardActiveStyle).toHaveProperty('background', 'var(--accent-hover)')
    expect(cardActiveStyle.borderLeft).toBe('3px solid var(--accent)')
  })

  it('cardStyle does not have active background', () => {
    expect(cardStyle.background).toBeUndefined()
    expect(cardStyle.borderLeft).toBe('3px solid var(--text-inactive)')
  })

  it('statusBadgeStyles has an entry for every statusColors key', () => {
    for (const key of Object.keys(statusColors)) {
      expect(statusBadgeStyles).toHaveProperty(key)
    }
  })

  it('each statusBadgeStyle includes base status style and correct bg/fg', () => {
    for (const [key, { bg, fg }] of Object.entries(statusColors)) {
      expect(statusBadgeStyles[key]).toMatchObject({
        fontSize: 11,
        padding: '2px 8px',
        borderRadius: 8,
        fontWeight: 600,
        background: bg,
        color: fg,
      })
    }
  })

  it('style objects are referentially stable', () => {
    expect(statusBadgeStyles.running).toBe(statusBadgeStyles.running)
    expect(cardActiveStyle).toBe(cardActiveStyle)
  })
})

const SIDEBAR_STAGES = PIPELINE_STAGES.filter(s => s.role != null)

describe('WorkerList section header styles', () => {
  it('sectionHeaderStyles has an entry for every sidebar pipeline stage', () => {
    for (const stage of SIDEBAR_STAGES) {
      expect(sectionHeaderStyles).toHaveProperty(stage.key)
      expect(sectionHeaderStyles[stage.key]).toMatchObject({
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 12px',
        cursor: 'pointer',
        userSelect: 'none',
        borderRadius: 6,
        transition: 'background 0.15s',
      })
      expect(sectionHeaderStyles[stage.key]).toHaveProperty('background')
      expect(sectionHeaderStyles[stage.key]).toHaveProperty('border')
      expect(sectionHeaderStyles[stage.key]).toHaveProperty('borderLeft')
    }
  })

  it('each sectionHeaderStyle uses the correct stage color', () => {
    for (const stage of SIDEBAR_STAGES) {
      const headerStyle = sectionHeaderStyles[stage.key]
      expect(headerStyle.background).toBe(stage.subtleColor)
      expect(headerStyle.borderLeft).toBe(`3px solid ${stage.color}`)
      expect(headerStyle.border).toBe(`1px solid ${stage.color}33`)
    }
  })

  it('sectionLabelStyles has correct color per stage', () => {
    for (const stage of SIDEBAR_STAGES) {
      const labelStyle = sectionLabelStyles[stage.key]
      expect(labelStyle.color).toBe(stage.color)
      expect(labelStyle).toMatchObject({
        fontSize: 11,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
      })
    }
  })

  it('sectionCountStyles has correct color per stage', () => {
    for (const stage of SIDEBAR_STAGES) {
      const countStyle = sectionCountStyles[stage.key]
      expect(countStyle.color).toBe(stage.color)
      expect(countStyle).toMatchObject({
        fontSize: 11,
        fontWeight: 600,
        marginLeft: 'auto',
      })
    }
  })

  it('section style objects are referentially stable', () => {
    expect(sectionHeaderStyles.triage).toBe(sectionHeaderStyles.triage)
    expect(sectionLabelStyles.triage).toBe(sectionLabelStyles.triage)
    expect(sectionCountStyles.triage).toBe(sectionCountStyles.triage)
  })
})

describe('WorkerList component', () => {
  it('renders without errors with empty workers', () => {
    render(<WorkerList workers={{}} selectedWorker={null} onSelect={() => {}} />)
    // Section headers should render pipeline stage names
    expect(screen.getByText('Triage')).toBeInTheDocument()
    expect(screen.getByText('Plan')).toBeInTheDocument()
    expect(screen.getByText('Implement')).toBeInTheDocument()
    expect(screen.getByText('Review')).toBeInTheDocument()
  })

  it('renders workers with reviewing and planning statuses', () => {
    const workers = {
      'review-1': { status: 'reviewing', title: 'Review PR', branch: 'feat', worker: 0, role: 'reviewer' },
      3: { status: 'planning', title: 'Plan issue', branch: '', worker: 1, role: 'planner' },
    }
    render(<WorkerList workers={workers} selectedWorker={null} onSelect={() => {}} />)
    expect(screen.getByText('reviewing')).toBeInTheDocument()
    expect(screen.getByText('planning')).toBeInTheDocument()
  })

  it('renders quality_fix worker with correct badge text', () => {
    const workers = {
      1: { status: 'quality_fix', title: 'Fix quality', branch: 'fix-branch', worker: 0, role: 'implementer' },
    }
    render(<WorkerList workers={workers} selectedWorker={null} onSelect={() => {}} />)
    expect(screen.getByText('quality_fix')).toBeInTheDocument()
  })

  it('renders merge_fix worker with correct badge text', () => {
    const workers = {
      1: { status: 'merge_fix', title: 'Resolve conflicts', branch: 'fix-branch', worker: 0, role: 'reviewer' },
    }
    render(<WorkerList workers={workers} selectedWorker={null} onSelect={() => {}} />)
    expect(screen.getByText('merge_fix')).toBeInTheDocument()
  })

  it('counts merge_fix workers as active in RoleSection', () => {
    const workers = {
      1: { status: 'merge_fix', title: 'Resolve conflicts', branch: 'fix-branch', worker: 0, role: 'reviewer' },
      2: { status: 'queued', title: 'Queued review', branch: '', worker: 1, role: 'reviewer' },
    }
    render(<WorkerList workers={workers} selectedWorker={null} onSelect={() => {}} />)
    expect(screen.getByText('1/2')).toBeInTheDocument()
  })

  it('counts quality_fix workers as active in RoleSection', () => {
    const workers = {
      1: { status: 'quality_fix', title: 'Fix quality', branch: 'fix-branch', worker: 0, role: 'implementer' },
      2: { status: 'queued', title: 'Queued issue', branch: '', worker: 1, role: 'implementer' },
    }
    render(<WorkerList workers={workers} selectedWorker={null} onSelect={() => {}} />)
    // Implement section should show 1/2 (1 active out of 2 total)
    expect(screen.getByText('1/2')).toBeInTheDocument()
  })

  it('renders workers with evaluating, validating, and fixing statuses', () => {
    const workers = {
      'triage-1': { status: 'evaluating', title: 'Triage Issue #1', branch: '', worker: 0, role: 'triage' },
      'plan-2': { status: 'validating', title: 'Plan Issue #2', branch: '', worker: 1, role: 'planner' },
      'review-3': { status: 'fixing', title: 'PR #3 (Issue #4)', branch: '', worker: 2, role: 'reviewer' },
    }
    render(<WorkerList workers={workers} selectedWorker={null} onSelect={() => {}} />)
    expect(screen.getByText('evaluating')).toBeInTheDocument()
    expect(screen.getByText('validating')).toBeInTheDocument()
    expect(screen.getByText('fixing')).toBeInTheDocument()
  })

  it('counts evaluating and fixing workers as active in RoleSection', () => {
    const workers = {
      'triage-1': { status: 'evaluating', title: 'Triage Issue #1', branch: '', worker: 0, role: 'triage' },
      'triage-2': { status: 'done', title: 'Triage Issue #2', branch: '', worker: 1, role: 'triage' },
    }
    render(<WorkerList workers={workers} selectedWorker={null} onSelect={() => {}} />)
    // Triage section should show 1/2 (1 active out of 2 total)
    expect(screen.getByText('1/2')).toBeInTheDocument()
  })

  it('renders workers with pre-computed styles', () => {
    const workers = {
      1: { status: 'running', title: 'Test issue', branch: 'test-branch', worker: 0, role: 'implementer' },
      2: { status: 'done', title: 'Done issue', branch: 'done-branch', worker: 1, role: 'implementer' },
    }
    render(<WorkerList workers={workers} selectedWorker={1} onSelect={() => {}} />)
    expect(screen.getByText('#1')).toBeInTheDocument()
    expect(screen.getByText('#2')).toBeInTheDocument()
    expect(screen.getByText('running')).toBeInTheDocument()
    expect(screen.getByText('done')).toBeInTheDocument()
  })
})
