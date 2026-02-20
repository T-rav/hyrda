import { describe, it, expect } from 'vitest'
import { ACTIVE_STATUSES } from '../constants'

describe('ACTIVE_STATUSES', () => {
  it('contains exactly the expected active statuses', () => {
    expect(ACTIVE_STATUSES).toEqual(['running', 'testing', 'committing', 'reviewing', 'planning'])
  })

  it('has 5 entries', () => {
    expect(ACTIVE_STATUSES).toHaveLength(5)
  })

  it('is an array of strings', () => {
    for (const status of ACTIVE_STATUSES) {
      expect(typeof status).toBe('string')
    }
  })
})
