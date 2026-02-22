import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { StreamCard, StatusDot, dotStyles, badgeStyleMap } from '../StreamCard'
import { theme } from '../../theme'
import { STAGE_KEYS } from '../../hooks/useTimeline'

function makeIssue(overrides = {}) {
  const stages = {}
  for (const key of STAGE_KEYS) {
    stages[key] = { status: 'pending', startTime: null, endTime: null, transcript: [] }
  }
  stages.plan = { status: 'active', startTime: null, endTime: null, transcript: [] }
  return {
    issueNumber: 42,
    title: 'Test issue',
    issueUrl: null,
    currentStage: 'plan',
    overallStatus: 'active',
    stages,
    pr: null,
    branch: 'agent/issue-42',
    startTime: null,
    endTime: null,
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

describe('StreamCard issue link', () => {
  it('renders issue number as a link when issueUrl is provided', () => {
    const issue = makeIssue({ issueUrl: 'https://github.com/owner/repo/issues/42' })
    render(<StreamCard issue={issue} />)
    const link = screen.getByText('#42')
    expect(link.tagName).toBe('A')
    expect(link.getAttribute('href')).toBe('https://github.com/owner/repo/issues/42')
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toBe('noopener noreferrer')
  })

  it('renders issue number as plain text when issueUrl is absent', () => {
    const issue = makeIssue({ issueUrl: null })
    render(<StreamCard issue={issue} />)
    const text = screen.getByText('#42')
    expect(text.tagName).toBe('SPAN')
  })

  it('link click does not toggle card expansion', () => {
    const issue = makeIssue({ issueUrl: 'https://github.com/owner/repo/issues/42' })
    const { container } = render(<StreamCard issue={issue} defaultExpanded={false} />)
    const link = screen.getByText('#42')
    fireEvent.click(link)
    // Card body should not appear — the card should remain collapsed
    expect(container.querySelector('[style*="border-top"]')).toBeNull()
  })
})
