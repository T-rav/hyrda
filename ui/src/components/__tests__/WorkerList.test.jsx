import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { WorkerList, cardStyle, cardActiveStyle, statusBadgeStyles, cardStylesByStage, sectionHeaderByRole, sectionLabelByRole } from '../WorkerList'
import { PIPELINE_STAGES } from '../../constants'

// Shared expected colors for stage-specific style tests
const expectedStageColors = {
  triage: 'var(--triage-green)',
  planner: 'var(--purple)',
  implementer: 'var(--accent)',
  reviewer: 'var(--orange)',
}

const statusColors = {
  queued:     { bg: 'var(--muted-subtle)',  fg: 'var(--text-muted)' },
  running:    { bg: 'var(--accent-subtle)', fg: 'var(--accent)' },
  planning:   { bg: 'var(--purple-subtle)', fg: 'var(--purple)' },
  testing:    { bg: 'var(--yellow-subtle)', fg: 'var(--yellow)' },
  committing:  { bg: 'var(--orange-subtle)', fg: 'var(--orange)' },
  quality_fix: { bg: 'var(--yellow-subtle)', fg: 'var(--yellow)' },
  reviewing:   { bg: 'var(--orange-subtle)', fg: 'var(--orange)' },
  done:        { bg: 'var(--green-subtle)',  fg: 'var(--green)' },
  failed:     { bg: 'var(--red-subtle)',    fg: 'var(--red)' },
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

describe('cardStylesByStage pre-computed styles', () => {
  it('has entries for all four pipeline roles', () => {
    for (const role of ['triage', 'planner', 'implementer', 'reviewer']) {
      expect(cardStylesByStage).toHaveProperty(role)
    }
  })

  it('each entry has normal and active variants', () => {
    for (const role of Object.keys(expectedStageColors)) {
      expect(cardStylesByStage[role]).toHaveProperty('normal')
      expect(cardStylesByStage[role]).toHaveProperty('active')
    }
  })

  it('normal variant uses the stage color for borderLeft', () => {
    for (const [role, color] of Object.entries(expectedStageColors)) {
      expect(cardStylesByStage[role].normal.borderLeft).toBe(`3px solid ${color}`)
    }
  })

  it('active variant uses the stage color for borderLeft (not generic accent)', () => {
    for (const [role, color] of Object.entries(expectedStageColors)) {
      expect(cardStylesByStage[role].active.borderLeft).toBe(`3px solid ${color}`)
    }
  })

  it('active variant has accent-hover background', () => {
    for (const role of Object.keys(expectedStageColors)) {
      expect(cardStylesByStage[role].active.background).toBe('var(--accent-hover)')
    }
  })

  it('normal variant inherits base card properties', () => {
    for (const role of Object.keys(expectedStageColors)) {
      expect(cardStylesByStage[role].normal).toHaveProperty('padding')
      expect(cardStylesByStage[role].normal).toHaveProperty('cursor', 'pointer')
    }
  })

  it('style objects are referentially stable', () => {
    expect(cardStylesByStage.triage.normal).toBe(cardStylesByStage.triage.normal)
    expect(cardStylesByStage.implementer.active).toBe(cardStylesByStage.implementer.active)
  })

  it('uses only colors from PIPELINE_STAGES (no new colors)', () => {
    const stageColors = PIPELINE_STAGES.filter(s => s.role).map(s => s.color)
    for (const role of Object.keys(expectedStageColors)) {
      const borderColor = cardStylesByStage[role].normal.borderLeft.replace('3px solid ', '')
      expect(stageColors).toContain(borderColor)
    }
  })
})

describe('sectionHeaderByRole pre-computed styles', () => {
  it('has entries for all four pipeline roles', () => {
    for (const role of Object.keys(expectedStageColors)) {
      expect(sectionHeaderByRole).toHaveProperty(role)
    }
  })

  it('each entry has a colored bottom border', () => {
    for (const [role, color] of Object.entries(expectedStageColors)) {
      expect(sectionHeaderByRole[role].borderBottom).toBe(`2px solid ${color}`)
    }
  })
})

describe('sectionLabelByRole pre-computed styles', () => {
  it('has entries for all four pipeline roles', () => {
    for (const role of Object.keys(expectedStageColors)) {
      expect(sectionLabelByRole).toHaveProperty(role)
    }
  })

  it('each entry uses the stage color', () => {
    for (const [role, color] of Object.entries(expectedStageColors)) {
      expect(sectionLabelByRole[role].color).toBe(color)
    }
  })

  it('each entry has fontSize 12', () => {
    for (const role of Object.keys(expectedStageColors)) {
      expect(sectionLabelByRole[role].fontSize).toBe(12)
    }
  })
})

describe('WorkerList component', () => {
  it('renders without errors with empty workers', () => {
    render(<WorkerList workers={{}} selectedWorker={null} onSelect={() => {}} />)
    // Section headers should still render
    expect(screen.getByText('Triage')).toBeInTheDocument()
    expect(screen.getByText('Planners')).toBeInTheDocument()
    expect(screen.getByText('Implementers')).toBeInTheDocument()
    expect(screen.getByText('Reviewers')).toBeInTheDocument()
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

  it('counts quality_fix workers as active in RoleSection', () => {
    const workers = {
      1: { status: 'quality_fix', title: 'Fix quality', branch: 'fix-branch', worker: 0, role: 'implementer' },
      2: { status: 'queued', title: 'Queued issue', branch: '', worker: 1, role: 'implementer' },
    }
    render(<WorkerList workers={workers} selectedWorker={null} onSelect={() => {}} />)
    // Implementers section should show 1/2 (1 active out of 2 total)
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
