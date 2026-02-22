import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { StatusDot, dotStyles, badgeStyleMap } from '../StreamCard'
import { theme } from '../../theme'

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
