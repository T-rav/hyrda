import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { StatusDot, dotStyles, badgeStyleMap, StreamCard } from '../StreamCard'
import { theme } from '../../theme'

const STAGE_KEYS = ['triage', 'plan', 'implement', 'review', 'merged']

function makeIssue(overrides = {}) {
  const stages = {}
  for (const k of STAGE_KEYS) {
    stages[k] = { status: 'pending', startTime: null, endTime: null, transcript: [] }
  }
  stages.review = { status: 'active', startTime: '2026-01-01T00:00:00Z', endTime: null, transcript: [] }
  return {
    issueNumber: 42,
    title: 'Fix the frobnicator',
    currentStage: 'review',
    overallStatus: 'active',
    startTime: '2026-01-01T00:00:00Z',
    endTime: null,
    pr: null,
    branch: 'agent/issue-42',
    stages,
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

describe('StreamCard request changes feedback flow', () => {
  it('shows feedback textarea on Request Changes click', () => {
    const issue = makeIssue()
    const onRequestChanges = vi.fn()
    render(<StreamCard issue={issue} defaultExpanded onRequestChanges={onRequestChanges} />)

    fireEvent.click(screen.getByTestId('request-changes-btn-42'))
    expect(screen.getByTestId('request-changes-textarea-42')).toBeTruthy()
  })

  it('hides feedback textarea on Cancel click', () => {
    const issue = makeIssue()
    const onRequestChanges = vi.fn()
    render(<StreamCard issue={issue} defaultExpanded onRequestChanges={onRequestChanges} />)

    fireEvent.click(screen.getByTestId('request-changes-btn-42'))
    expect(screen.getByTestId('request-changes-textarea-42')).toBeTruthy()

    fireEvent.click(screen.getByTestId('request-changes-cancel-42'))
    expect(screen.queryByTestId('request-changes-textarea-42')).toBeNull()
  })

  it('disables submit when feedback is empty', () => {
    const issue = makeIssue()
    const onRequestChanges = vi.fn()
    render(<StreamCard issue={issue} defaultExpanded onRequestChanges={onRequestChanges} />)

    fireEvent.click(screen.getByTestId('request-changes-btn-42'))
    const submitBtn = screen.getByTestId('request-changes-submit-42')
    expect(submitBtn.disabled).toBe(true)
  })

  it('calls onRequestChanges with correct arguments on submit', async () => {
    const issue = makeIssue()
    const onRequestChanges = vi.fn(() => Promise.resolve())
    render(<StreamCard issue={issue} defaultExpanded onRequestChanges={onRequestChanges} />)

    fireEvent.click(screen.getByTestId('request-changes-btn-42'))
    const textarea = screen.getByTestId('request-changes-textarea-42')
    fireEvent.change(textarea, { target: { value: 'Fix the tests please' } })

    const submitBtn = screen.getByTestId('request-changes-submit-42')
    expect(submitBtn.disabled).toBe(false)
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(onRequestChanges).toHaveBeenCalledWith(42, 'Fix the tests please', 'review')
    })
  })

  it('shows placeholder text on textarea', () => {
    const issue = makeIssue()
    const onRequestChanges = vi.fn()
    render(<StreamCard issue={issue} defaultExpanded onRequestChanges={onRequestChanges} />)

    fireEvent.click(screen.getByTestId('request-changes-btn-42'))
    const textarea = screen.getByTestId('request-changes-textarea-42')
    expect(textarea.placeholder).toBe('What needs to change?')
  })

  it('does not show Request Changes button when onRequestChanges is not provided', () => {
    const issue = makeIssue()
    render(<StreamCard issue={issue} defaultExpanded />)

    expect(screen.queryByTestId('request-changes-btn-42')).toBeNull()
  })

  it('closes feedback panel after successful submit', async () => {
    const issue = makeIssue()
    const onRequestChanges = vi.fn().mockResolvedValue(true)
    render(<StreamCard issue={issue} defaultExpanded onRequestChanges={onRequestChanges} />)

    fireEvent.click(screen.getByTestId('request-changes-btn-42'))
    fireEvent.change(screen.getByTestId('request-changes-textarea-42'), {
      target: { value: 'Fix the tests' },
    })
    fireEvent.click(screen.getByTestId('request-changes-submit-42'))

    await waitFor(() => {
      expect(screen.queryByTestId('request-changes-textarea-42')).toBeNull()
    })
  })

  it('keeps feedback panel open after failed submit', async () => {
    const issue = makeIssue()
    const onRequestChanges = vi.fn().mockResolvedValue(false)
    render(<StreamCard issue={issue} defaultExpanded onRequestChanges={onRequestChanges} />)

    fireEvent.click(screen.getByTestId('request-changes-btn-42'))
    fireEvent.change(screen.getByTestId('request-changes-textarea-42'), {
      target: { value: 'Fix the tests' },
    })
    fireEvent.click(screen.getByTestId('request-changes-submit-42'))

    await waitFor(() => {
      expect(onRequestChanges).toHaveBeenCalled()
    })
    expect(screen.getByTestId('request-changes-textarea-42')).toBeTruthy()
  })
})
