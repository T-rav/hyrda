import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { StatusDot, dotStyles, badgeStyleMap } from '../StreamCard'
import { StreamCard } from '../StreamCard'
import { STAGE_KEYS } from '../../hooks/useTimeline'
import { theme } from '../../theme'

function makeIssue(overrides = {}) {
  const stages = Object.fromEntries(
    STAGE_KEYS.map(k => [k, { status: 'pending', startTime: null, endTime: null, transcript: [] }])
  )
  return {
    issueNumber: 1,
    title: 'Test issue',
    currentStage: 'implement',
    overallStatus: 'active',
    startTime: null,
    endTime: null,
    pr: null,
    branch: 'agent/issue-1',
    stages: { ...stages, triage: { ...stages.triage, status: 'done' }, plan: { ...stages.plan, status: 'done' }, implement: { ...stages.implement, status: 'active' } },
    ...overrides,
  }
}

describe('StatusDot component', () => {
  it('renders a pulsing dot for active status', () => {
    const { container } = render(<StatusDot status="active" />)
    const el = container.firstChild
    expect(el.tagName).toBe('SPAN')
    expect(el.style.animation).toContain('stream-pulse')
    expect(el.style.background).toBe(theme.accent)
  })

  it('renders a checkmark for done status', () => {
    const { container } = render(<StatusDot status="done" />)
    expect(container.textContent).toBe('\u2713')
  })

  it('renders an X mark for failed status', () => {
    const { container } = render(<StatusDot status="failed" />)
    expect(container.textContent).toBe('\u2717')
  })

  it('renders an exclamation for hitl status', () => {
    const { container } = render(<StatusDot status="hitl" />)
    expect(container.textContent).toBe('!')
  })

  it('renders a static yellow dot for queued status', () => {
    const { container } = render(<StatusDot status="queued" />)
    const el = container.firstChild
    expect(el.tagName).toBe('SPAN')
    expect(el.style.background).toBe(theme.yellow)
    expect(el.style.animation).toBe('')
  })

  it('renders a static grey dot for pending status', () => {
    const { container } = render(<StatusDot status="pending" />)
    const el = container.firstChild
    expect(el.tagName).toBe('SPAN')
    expect(el.style.background).toBe(theme.border)
    expect(el.style.animation).toBe('')
  })
})

describe('dotStyles', () => {
  it('has entries for all supported statuses', () => {
    const expectedStatuses = ['active', 'done', 'failed', 'hitl', 'queued', 'pending']
    for (const status of expectedStatuses) {
      expect(dotStyles).toHaveProperty(status)
    }
  })

  it('active style has pulse animation', () => {
    expect(dotStyles.active.animation).toContain('stream-pulse')
  })

  it('queued style has yellow background and no animation', () => {
    expect(dotStyles.queued.background).toBe(theme.yellow)
    expect(dotStyles.queued).not.toHaveProperty('animation')
  })

  it('pending style has border color background and no animation', () => {
    expect(dotStyles.pending.background).toBe(theme.border)
    expect(dotStyles.pending).not.toHaveProperty('animation')
  })
})

describe('badgeStyleMap', () => {
  it('has entries for all supported statuses including queued', () => {
    const expectedStatuses = ['active', 'done', 'failed', 'hitl', 'queued', 'pending']
    for (const status of expectedStatuses) {
      expect(badgeStyleMap).toHaveProperty(status)
    }
  })

  it('queued badge uses yellow theme colors', () => {
    expect(badgeStyleMap.queued.background).toBe(theme.yellowSubtle)
    expect(badgeStyleMap.queued.color).toBe(theme.yellow)
  })
})

describe('StreamCard transcript rendering', () => {
  it('renders TranscriptPreview when active and transcript is non-empty', () => {
    const issue = makeIssue({ overallStatus: 'active' })
    render(<StreamCard issue={issue} defaultExpanded={true} transcript={['line 1', 'line 2', 'line 3']} />)
    expect(screen.getByTestId('transcript-preview')).toBeInTheDocument()
    expect(screen.getByText('line 1')).toBeInTheDocument()
    expect(screen.getByText('line 2')).toBeInTheDocument()
    expect(screen.getByText('line 3')).toBeInTheDocument()
  })

  it('does not render TranscriptPreview when status is queued', () => {
    const issue = makeIssue({ overallStatus: 'queued' })
    render(<StreamCard issue={issue} defaultExpanded={true} transcript={['line 1']} />)
    expect(screen.queryByTestId('transcript-preview')).not.toBeInTheDocument()
  })

  it('does not render TranscriptPreview when status is done', () => {
    const issue = makeIssue({ overallStatus: 'done' })
    render(<StreamCard issue={issue} defaultExpanded={true} transcript={['line 1']} />)
    expect(screen.queryByTestId('transcript-preview')).not.toBeInTheDocument()
  })

  it('does not render TranscriptPreview when status is failed', () => {
    const issue = makeIssue({ overallStatus: 'failed' })
    render(<StreamCard issue={issue} defaultExpanded={true} transcript={['line 1']} />)
    expect(screen.queryByTestId('transcript-preview')).not.toBeInTheDocument()
  })

  it('does not render TranscriptPreview when transcript is empty', () => {
    const issue = makeIssue({ overallStatus: 'active' })
    render(<StreamCard issue={issue} defaultExpanded={true} transcript={[]} />)
    expect(screen.queryByTestId('transcript-preview')).not.toBeInTheDocument()
  })

  it('does not render TranscriptPreview when card is collapsed', () => {
    const issue = makeIssue({ overallStatus: 'active' })
    render(<StreamCard issue={issue} defaultExpanded={false} transcript={['line 1']} />)
    expect(screen.queryByTestId('transcript-preview')).not.toBeInTheDocument()
  })

  it('defaults transcript to empty array when not provided', () => {
    const issue = makeIssue({ overallStatus: 'active' })
    render(<StreamCard issue={issue} defaultExpanded={true} />)
    expect(screen.queryByTestId('transcript-preview')).not.toBeInTheDocument()
  })
})
