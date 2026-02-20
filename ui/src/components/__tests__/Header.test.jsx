import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  Header,
  dotConnected, dotDisconnected,
  pillStyles, headerConnectorStyles,
  countLit, countDim,
  startBtnEnabled, startBtnDisabled,
} from '../Header'

const STAGE_KEYS = ['triage', 'plan', 'implement', 'review']
const STAGE_COLORS = {
  triage: '#39d353',
  plan: '#a371f7',
  implement: '#58a6ff',
  review: '#d18616',
}

describe('Header pre-computed styles', () => {
  describe('dot variants', () => {
    it('dotConnected has green background', () => {
      expect(dotConnected).toMatchObject({
        width: 8, height: 8, borderRadius: '50%',
        background: '#3fb950',
      })
    })

    it('dotDisconnected has red background', () => {
      expect(dotDisconnected).toMatchObject({
        width: 8, height: 8, borderRadius: '50%',
        background: '#f85149',
      })
    })
  })

  describe('pill styles', () => {
    it('has entries for each stage', () => {
      for (const key of STAGE_KEYS) {
        expect(pillStyles).toHaveProperty(key)
        expect(pillStyles[key]).toHaveProperty('lit')
        expect(pillStyles[key]).toHaveProperty('dim')
      }
    })

    it('lit variant uses stage color for background', () => {
      for (const key of STAGE_KEYS) {
        expect(pillStyles[key].lit.background).toBe(STAGE_COLORS[key])
        expect(pillStyles[key].lit.color).toBe('#0d1117')
        expect(pillStyles[key].lit.borderColor).toBe(STAGE_COLORS[key])
      }
    })

    it('dim variant uses color with opacity suffixes', () => {
      for (const key of STAGE_KEYS) {
        expect(pillStyles[key].dim.background).toBe(STAGE_COLORS[key] + '20')
        expect(pillStyles[key].dim.color).toBe(STAGE_COLORS[key] + '99')
        expect(pillStyles[key].dim.borderColor).toBe(STAGE_COLORS[key] + '55')
      }
    })

    it('pill variants include base pill properties', () => {
      for (const key of STAGE_KEYS) {
        expect(pillStyles[key].lit).toMatchObject({
          padding: '4px 14px',
          borderRadius: 12,
          fontSize: 11,
          fontWeight: 600,
        })
      }
    })
  })

  describe('header connector styles', () => {
    it('has entries for each stage with lit/dim sub-keys', () => {
      for (const key of STAGE_KEYS) {
        expect(headerConnectorStyles).toHaveProperty(key)
        expect(headerConnectorStyles[key]).toHaveProperty('lit')
        expect(headerConnectorStyles[key]).toHaveProperty('dim')
      }
    })

    it('lit variant uses stage color, dim uses color + 55', () => {
      for (const key of STAGE_KEYS) {
        expect(headerConnectorStyles[key].lit.background).toBe(STAGE_COLORS[key])
        expect(headerConnectorStyles[key].dim.background).toBe(STAGE_COLORS[key] + '55')
      }
    })

    it('connector variants include base connector properties', () => {
      for (const key of STAGE_KEYS) {
        expect(headerConnectorStyles[key].lit).toMatchObject({ width: 24, height: 2, flexShrink: 0 })
      }
    })
  })

  describe('count styles', () => {
    it('countLit has opacity 1', () => {
      expect(countLit.opacity).toBe(1)
      expect(countLit).toMatchObject({ borderRadius: 8, fontSize: 10, fontWeight: 700 })
    })

    it('countDim has opacity 0.6', () => {
      expect(countDim.opacity).toBe(0.6)
    })
  })

  describe('start button variants', () => {
    it('startBtnEnabled has opacity 1 and pointer cursor', () => {
      expect(startBtnEnabled).toMatchObject({ opacity: 1, cursor: 'pointer' })
      expect(startBtnEnabled.background).toBe('#238636')
    })

    it('startBtnDisabled has opacity 0.4 and not-allowed cursor', () => {
      expect(startBtnDisabled).toMatchObject({ opacity: 0.4, cursor: 'not-allowed' })
    })
  })

  it('style objects are referentially stable', () => {
    expect(dotConnected).toBe(dotConnected)
    expect(pillStyles.plan.lit).toBe(pillStyles.plan.lit)
    expect(startBtnEnabled).toBe(startBtnEnabled)
  })
})

describe('Header component', () => {
  const defaultProps = {
    prsCount: 0,
    mergedCount: 0,
    issuesFound: 0,
    connected: true,
    orchestratorStatus: 'idle',
    onStart: () => {},
    onStop: () => {},
    phase: 'idle',
    workers: {},
    config: { max_planners: 2, max_workers: 4, max_reviewers: 2 },
  }

  it('renders without errors', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByText('HYDRA')).toBeInTheDocument()
  })

  it('renders Start button when idle', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByText('Start')).toBeInTheDocument()
  })

  it('renders Stop button when running', () => {
    render(<Header {...defaultProps} orchestratorStatus="running" />)
    expect(screen.getByText('Stop')).toBeInTheDocument()
  })

  it('renders stage pills', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByText('TRIAGE')).toBeInTheDocument()
    expect(screen.getByText('PLAN')).toBeInTheDocument()
    expect(screen.getByText('IMPLEMENT')).toBeInTheDocument()
    expect(screen.getByText('REVIEW')).toBeInTheDocument()
  })
})
