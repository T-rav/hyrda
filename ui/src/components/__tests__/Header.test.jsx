import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  Header,
  dotConnected, dotDisconnected,
  pillStyles, headerConnectorStyles,
  sessionPillStyles, sessionConnectorStyles,
  countLit, countDim,
  startBtnEnabled, startBtnDisabled,
} from '../Header'

const STAGE_KEYS = ['triage', 'plan', 'implement', 'review']
const SESSION_STAGE_KEYS = ['triage', 'plan', 'implement', 'review', 'merged']
const STAGE_COLORS = {
  triage: 'var(--triage-green)',
  plan: 'var(--purple)',
  implement: 'var(--accent)',
  review: 'var(--orange)',
  merged: 'var(--green)',
}

describe('Header pre-computed styles', () => {
  describe('dot variants', () => {
    it('dotConnected has green background', () => {
      expect(dotConnected).toMatchObject({
        width: 8, height: 8, borderRadius: '50%',
        background: 'var(--green)',
      })
    })

    it('dotDisconnected has red background', () => {
      expect(dotDisconnected).toMatchObject({
        width: 8, height: 8, borderRadius: '50%',
        background: 'var(--red)',
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
        expect(pillStyles[key].lit.color).toBe('var(--bg)')
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
          padding: '2px 8px',
          borderRadius: 10,
          fontSize: 10,
          fontWeight: 600,
        })
      }
    })

    it('pill and session pill styles share the same dimensions', () => {
      // Both pill types should use identical padding, fontSize, borderRadius
      for (const key of STAGE_KEYS) {
        expect(pillStyles[key].dim.padding).toBe(sessionPillStyles[key].padding)
        expect(pillStyles[key].dim.borderRadius).toBe(sessionPillStyles[key].borderRadius)
        expect(pillStyles[key].dim.fontSize).toBe(sessionPillStyles[key].fontSize)
      }
    })
  })

  describe('session pill styles', () => {
    it('has entries for all 5 session stages including merged', () => {
      for (const key of SESSION_STAGE_KEYS) {
        expect(sessionPillStyles).toHaveProperty(key)
      }
    })

    it('uses correct color with opacity suffix for each stage', () => {
      for (const key of SESSION_STAGE_KEYS) {
        expect(sessionPillStyles[key].background).toBe(STAGE_COLORS[key] + '20')
        expect(sessionPillStyles[key].color).toBe(STAGE_COLORS[key])
        expect(sessionPillStyles[key].borderColor).toBe(STAGE_COLORS[key] + '44')
      }
    })

    it('session pill styles include base sessionPill properties', () => {
      for (const key of SESSION_STAGE_KEYS) {
        expect(sessionPillStyles[key]).toMatchObject({
          padding: '2px 8px',
          borderRadius: 10,
          fontSize: 10,
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

  describe('session connector styles', () => {
    it('has entries for all 5 session stages', () => {
      for (const key of SESSION_STAGE_KEYS) {
        expect(sessionConnectorStyles).toHaveProperty(key)
      }
    })

    it('uses stage color with opacity suffix for background', () => {
      for (const key of SESSION_STAGE_KEYS) {
        expect(sessionConnectorStyles[key].background).toBe(STAGE_COLORS[key] + '55')
      }
    })

    it('connector has compact dimensions (thinner than process connectors)', () => {
      for (const key of SESSION_STAGE_KEYS) {
        expect(sessionConnectorStyles[key]).toMatchObject({ width: 12, height: 1, flexShrink: 0 })
      }
    })

    it('session connectors are thinner than process connectors', () => {
      const sessionConn = sessionConnectorStyles.plan
      const processConn = headerConnectorStyles.plan.lit
      expect(sessionConn.width).toBeLessThan(processConn.width)
      expect(sessionConn.height).toBeLessThan(processConn.height)
    })
  })

  describe('count styles', () => {
    it('countLit has opacity 1', () => {
      expect(countLit.opacity).toBe(1)
      expect(countLit).toMatchObject({ borderRadius: 6, fontSize: 9, fontWeight: 700 })
    })

    it('countDim has opacity 0.6', () => {
      expect(countDim.opacity).toBe(0.6)
    })
  })

  describe('start button variants', () => {
    it('startBtnEnabled has opacity 1 and pointer cursor', () => {
      expect(startBtnEnabled).toMatchObject({ opacity: 1, cursor: 'pointer' })
      expect(startBtnEnabled.background).toBe('var(--btn-green)')
    })

    it('startBtnDisabled has opacity 0.4 and not-allowed cursor', () => {
      expect(startBtnDisabled).toMatchObject({ opacity: 0.4, cursor: 'not-allowed' })
    })
  })

  it('style objects are referentially stable', () => {
    expect(dotConnected).toBe(dotConnected)
    expect(pillStyles.plan.lit).toBe(pillStyles.plan.lit)
    expect(startBtnEnabled).toBe(startBtnEnabled)
    expect(sessionPillStyles.triage).toBe(sessionPillStyles.triage)
  })
})

describe('Header component', () => {
  const defaultProps = {
    sessionCounts: { triage: 0, plan: 0, implement: 0, review: 0, merged: 0 },
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

  it('renders pipeline stage pills', () => {
    render(<Header {...defaultProps} />)
    // Pipeline pills render TRIAGE, PLAN, IMPLEMENT, REVIEW
    // Session pills also render these plus MERGED
    expect(screen.getAllByText('TRIAGE').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('PLAN').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('IMPLEMENT').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('REVIEW').length).toBeGreaterThanOrEqual(1)
  })

  it('renders session pills with all 5 stage labels', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByText('MERGED')).toBeInTheDocument()
    // Each stage appears twice: once in session pills, once in pipeline pills (except MERGED)
    expect(screen.getAllByText('TRIAGE')).toHaveLength(2)
    expect(screen.getAllByText('PLAN')).toHaveLength(2)
    expect(screen.getAllByText('IMPLEMENT')).toHaveLength(2)
    expect(screen.getAllByText('REVIEW')).toHaveLength(2)
    expect(screen.getAllByText('MERGED')).toHaveLength(1)
  })

  it('renders session pill counts correctly', () => {
    const counts = { triage: 3, plan: 5, implement: 4, review: 2, merged: 7 }
    render(<Header {...defaultProps} sessionCounts={counts} />)
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
  })

  it('renders session pill counts as 0 when all zero', () => {
    render(<Header {...defaultProps} />)
    // All 5 session pills show 0, plus pipeline pills show config counts
    const zeros = screen.getAllByText('0')
    expect(zeros.length).toBeGreaterThanOrEqual(5)
  })

  it('renders workload summary with empty workers', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByText('0 total')).toBeInTheDocument()
    expect(screen.getByText('0 active')).toBeInTheDocument()
    expect(screen.getByText('0 done')).toBeInTheDocument()
    expect(screen.getByText('0 failed')).toBeInTheDocument()
  })

  it('renders workload summary with workers in various statuses', () => {
    const workers = {
      1: { status: 'running', worker: 1, role: 'implementer', title: 'Issue #1', branch: '', transcript: [], pr: null },
      2: { status: 'running', worker: 2, role: 'implementer', title: 'Issue #2', branch: '', transcript: [], pr: null },
      3: { status: 'done', worker: 3, role: 'implementer', title: 'Issue #3', branch: '', transcript: [], pr: null },
      4: { status: 'done', worker: 4, role: 'planner', title: 'Plan #4', branch: '', transcript: [], pr: null },
      5: { status: 'failed', worker: 5, role: 'implementer', title: 'Issue #5', branch: '', transcript: [], pr: null },
    }
    render(<Header {...defaultProps} workers={workers} />)
    expect(screen.getByText('5 total')).toBeInTheDocument()
    expect(screen.getByText('2 active')).toBeInTheDocument()
    expect(screen.getByText('2 done')).toBeInTheDocument()
    expect(screen.getByText('1 failed')).toBeInTheDocument()
  })

  it('counts quality_fix workers as active in workload summary', () => {
    const workers = {
      1: { status: 'quality_fix', worker: 1, role: 'implementer', title: 'Fix #1', branch: '', transcript: [], pr: null },
      2: { status: 'queued', worker: 2, role: 'implementer', title: 'Issue #2', branch: '', transcript: [], pr: null },
    }
    render(<Header {...defaultProps} workers={workers} />)
    expect(screen.getByText('2 total')).toBeInTheDocument()
    expect(screen.getByText('1 active')).toBeInTheDocument()
  })

  it('renders connector lines between session pills instead of arrows', () => {
    render(<Header {...defaultProps} />)
    // No arrow characters should be rendered
    expect(screen.queryByText('\u2192')).toBeNull()
    // 5 session stages means 4 connectors rendered as divs with testid
    const connectors = screen.getAllByTestId('session-connector')
    expect(connectors.length).toBe(4)
  })

  it('renders Session label', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByText('Session')).toBeInTheDocument()
  })
})
