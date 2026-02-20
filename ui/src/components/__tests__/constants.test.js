import { describe, it, expect } from 'vitest'
import { ACTIVE_STATUSES, PIPELINE_STAGES } from '../../constants'
import { theme } from '../../theme'

describe('ACTIVE_STATUSES', () => {
  it('is an array', () => {
    expect(Array.isArray(ACTIVE_STATUSES)).toBe(true)
  })

  it('contains expected active statuses', () => {
    expect(ACTIVE_STATUSES).toEqual([
      'running', 'testing', 'committing', 'reviewing', 'planning', 'quality_fix',
      'start', 'merge_main', 'conflict_resolution', 'ci_wait', 'ci_fix', 'merging',
    ])
  })

  it('includes quality_fix status', () => {
    expect(ACTIVE_STATUSES).toContain('quality_fix')
  })

  it('does not include terminal statuses', () => {
    const terminalStatuses = ['queued', 'done', 'failed']
    for (const status of terminalStatuses) {
      expect(ACTIVE_STATUSES).not.toContain(status)
    }
  })
})

describe('PIPELINE_STAGES', () => {
  it('is an array with 5 stages', () => {
    expect(Array.isArray(PIPELINE_STAGES)).toBe(true)
    expect(PIPELINE_STAGES).toHaveLength(5)
  })

  it('contains all pipeline stage keys in order', () => {
    const keys = PIPELINE_STAGES.map(s => s.key)
    expect(keys).toEqual(['triage', 'plan', 'implement', 'review', 'merged'])
  })

  it('has title-case labels for each stage', () => {
    const labels = PIPELINE_STAGES.map(s => s.label)
    expect(labels).toEqual(['Triage', 'Plan', 'Implement', 'Review', 'Merged'])
  })

  it('maps each stage to the correct theme color', () => {
    const colorMap = Object.fromEntries(PIPELINE_STAGES.map(s => [s.key, s.color]))
    expect(colorMap).toEqual({
      triage: theme.triageGreen,
      plan: theme.purple,
      implement: theme.accent,
      review: theme.orange,
      merged: theme.green,
    })
  })

  it('assigns roles to active stages and null to merged', () => {
    const roleMap = Object.fromEntries(PIPELINE_STAGES.map(s => [s.key, s.role]))
    expect(roleMap).toEqual({
      triage: 'triage',
      plan: 'planner',
      implement: 'implementer',
      review: 'reviewer',
      merged: null,
    })
  })

  it('assigns configKeys to plan, implement, review and null to triage/merged', () => {
    const configMap = Object.fromEntries(PIPELINE_STAGES.map(s => [s.key, s.configKey]))
    expect(configMap).toEqual({
      triage: null,
      plan: 'max_planners',
      implement: 'max_workers',
      review: 'max_reviewers',
      merged: null,
    })
  })

  it('maps each stage to the correct subtle color', () => {
    const subtleMap = Object.fromEntries(PIPELINE_STAGES.map(s => [s.key, s.subtleColor]))
    expect(subtleMap).toEqual({
      triage: theme.greenSubtle,
      plan: theme.purpleSubtle,
      implement: theme.accentSubtle,
      review: theme.orangeSubtle,
      merged: theme.greenSubtle,
    })
  })

  it('every stage has key, label, color, subtleColor, role, and configKey properties', () => {
    for (const stage of PIPELINE_STAGES) {
      expect(stage).toHaveProperty('key')
      expect(stage).toHaveProperty('label')
      expect(stage).toHaveProperty('color')
      expect(stage).toHaveProperty('subtleColor')
      expect(stage).toHaveProperty('role')
      expect(stage).toHaveProperty('configKey')
    }
  })

  it('has unique keys', () => {
    const keys = PIPELINE_STAGES.map(s => s.key)
    expect(new Set(keys).size).toBe(keys.length)
  })
})
