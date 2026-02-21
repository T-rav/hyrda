import { describe, it, expect } from 'vitest'
import { toStreamIssue } from '../StreamView'
import { STAGE_KEYS } from '../../hooks/useTimeline'

const basePipeIssue = {
  issue_number: 42,
  title: 'Test issue',
  url: 'https://github.com/test/42',
}

describe('toStreamIssue status mapping', () => {
  it('maps active status to overallStatus active', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'plan', [])
    expect(result.overallStatus).toBe('active')
  })

  it('maps queued status to overallStatus queued', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'queued' }, 'plan', [])
    expect(result.overallStatus).toBe('queued')
  })

  it('maps hitl status to overallStatus hitl', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'hitl' }, 'plan', [])
    expect(result.overallStatus).toBe('hitl')
  })

  it('maps failed status to overallStatus failed', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'failed' }, 'plan', [])
    expect(result.overallStatus).toBe('failed')
  })

  it('maps error status to overallStatus failed', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'error' }, 'plan', [])
    expect(result.overallStatus).toBe('failed')
  })

  it('maps done status to overallStatus done', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'done' }, 'merged', [])
    expect(result.overallStatus).toBe('done')
  })

  it('maps unknown status to overallStatus queued', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'something_else' }, 'plan', [])
    expect(result.overallStatus).toBe('queued')
  })

  it('defaults to queued when status is undefined', () => {
    const result = toStreamIssue({ ...basePipeIssue }, 'plan', [])
    expect(result.overallStatus).toBe('queued')
  })
})

describe('toStreamIssue stage building', () => {
  it('sets current stage to active when issue status is active', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'implement', [])
    expect(result.stages.implement.status).toBe('active')
  })

  it('sets current stage to queued when issue status is not active', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'queued' }, 'implement', [])
    expect(result.stages.implement.status).toBe('queued')
  })

  it('sets prior stages to done', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'review', [])
    expect(result.stages.triage.status).toBe('done')
    expect(result.stages.plan.status).toBe('done')
    expect(result.stages.implement.status).toBe('done')
  })

  it('sets later stages to pending', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'plan', [])
    expect(result.stages.implement.status).toBe('pending')
    expect(result.stages.review.status).toBe('pending')
    expect(result.stages.merged.status).toBe('pending')
  })
})

describe('toStreamIssue output shape', () => {
  it('returns correct issueNumber and title', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'plan', [])
    expect(result.issueNumber).toBe(42)
    expect(result.title).toBe('Test issue')
  })

  it('returns currentStage matching the stageKey argument', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'implement', [])
    expect(result.currentStage).toBe('implement')
  })

  it('builds a stages object with all STAGE_KEYS', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'plan', [])
    for (const key of STAGE_KEYS) {
      expect(result.stages).toHaveProperty(key)
      expect(result.stages[key]).toHaveProperty('status')
      expect(result.stages[key]).toHaveProperty('startTime')
      expect(result.stages[key]).toHaveProperty('endTime')
      expect(result.stages[key]).toHaveProperty('transcript')
    }
  })

  it('matches PR from prs array by issue_number', () => {
    const prs = [{ issue: 42, pr: 100, url: 'https://github.com/pr/100' }]
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'review', prs)
    expect(result.pr).toEqual({ number: 100, url: 'https://github.com/pr/100' })
  })

  it('returns null pr when no matching PR exists', () => {
    const result = toStreamIssue({ ...basePipeIssue, status: 'active' }, 'plan', [])
    expect(result.pr).toBeNull()
  })
})
