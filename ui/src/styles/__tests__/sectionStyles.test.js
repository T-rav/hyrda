import { describe, it, expect } from 'vitest'
import { PIPELINE_STAGES } from '../../constants'
import {
  sectionHeaderBase,
  sectionLabelBase,
  sectionCountBase,
  sectionHeaderStyles,
  sectionLabelStyles,
  sectionCountStyles,
} from '../sectionStyles'

describe('sectionStyles shared module', () => {
  const stageKeys = PIPELINE_STAGES.map(s => s.key)

  describe('sectionHeaderStyles', () => {
    it('has an entry for every PIPELINE_STAGES key', () => {
      for (const key of stageKeys) {
        expect(sectionHeaderStyles).toHaveProperty(key)
      }
    })

    it('includes all base properties in each entry', () => {
      for (const key of stageKeys) {
        const style = sectionHeaderStyles[key]
        for (const prop of Object.keys(sectionHeaderBase)) {
          expect(style).toHaveProperty(prop, sectionHeaderBase[prop])
        }
      }
    })

    it('applies correct stage-specific background, border, and borderLeft', () => {
      for (const stage of PIPELINE_STAGES) {
        const style = sectionHeaderStyles[stage.key]
        expect(style.background).toBe(stage.subtleColor)
        expect(style.border).toBe(`1px solid ${stage.color}33`)
        expect(style.borderLeft).toBe(`3px solid ${stage.color}`)
      }
    })
  })

  describe('sectionLabelStyles', () => {
    it('has an entry for every PIPELINE_STAGES key', () => {
      for (const key of stageKeys) {
        expect(sectionLabelStyles).toHaveProperty(key)
      }
    })

    it('includes all base properties in each entry', () => {
      for (const key of stageKeys) {
        const style = sectionLabelStyles[key]
        for (const prop of Object.keys(sectionLabelBase)) {
          expect(style).toHaveProperty(prop, sectionLabelBase[prop])
        }
      }
    })

    it('applies correct stage color', () => {
      for (const stage of PIPELINE_STAGES) {
        expect(sectionLabelStyles[stage.key].color).toBe(stage.color)
      }
    })
  })

  describe('sectionCountStyles', () => {
    it('has an entry for every PIPELINE_STAGES key', () => {
      for (const key of stageKeys) {
        expect(sectionCountStyles).toHaveProperty(key)
      }
    })

    it('includes all base properties in each entry', () => {
      for (const key of stageKeys) {
        const style = sectionCountStyles[key]
        for (const prop of Object.keys(sectionCountBase)) {
          expect(style).toHaveProperty(prop, sectionCountBase[prop])
        }
      }
    })

    it('applies correct stage color', () => {
      for (const stage of PIPELINE_STAGES) {
        expect(sectionCountStyles[stage.key].color).toBe(stage.color)
      }
    })
  })

  describe('referential stability', () => {
    it('returns the same object on repeated access', () => {
      for (const key of stageKeys) {
        expect(sectionHeaderStyles[key]).toBe(sectionHeaderStyles[key])
        expect(sectionLabelStyles[key]).toBe(sectionLabelStyles[key])
        expect(sectionCountStyles[key]).toBe(sectionCountStyles[key])
      }
    })
  })
})
