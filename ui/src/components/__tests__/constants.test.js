import { describe, it, expect } from 'vitest'
import { ACTIVE_STATUSES } from '../../constants'

describe('ACTIVE_STATUSES', () => {
  it('is an array', () => {
    expect(Array.isArray(ACTIVE_STATUSES)).toBe(true)
  })

  it('contains expected active statuses', () => {
    expect(ACTIVE_STATUSES).toEqual([
      'running', 'testing', 'committing', 'reviewing', 'planning',
    ])
  })

  it('does not include terminal statuses', () => {
    const terminalStatuses = ['queued', 'done', 'failed']
    for (const status of terminalStatuses) {
      expect(ACTIVE_STATUSES).not.toContain(status)
    }
  })
})
