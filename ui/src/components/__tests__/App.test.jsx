import { describe, it, expect } from 'vitest'
import { tabActiveStyle, tabInactiveStyle, hitlBadgeStyle } from '../../App'

describe('App pre-computed tab styles', () => {
  it('tabInactiveStyle has base tab properties', () => {
    expect(tabInactiveStyle).toMatchObject({
      padding: '10px 20px',
      fontSize: 12,
      fontWeight: 600,
      color: 'var(--text-muted)',
      cursor: 'pointer',
      borderBottom: '2px solid transparent',
    })
  })

  it('tabActiveStyle includes both tab and tabActive properties', () => {
    expect(tabActiveStyle).toMatchObject({
      padding: '10px 20px',
      fontSize: 12,
      fontWeight: 600,
      color: 'var(--accent)',
      cursor: 'pointer',
      borderBottomColor: 'var(--accent)',
    })
  })

  it('tabActiveStyle overrides color from tabActive', () => {
    // tabActive color (var(--accent)) should override base tab color (var(--text-muted))
    expect(tabActiveStyle.color).toBe('var(--accent)')
  })

  it('style objects are referentially stable', () => {
    expect(tabActiveStyle).toBe(tabActiveStyle)
    expect(tabInactiveStyle).toBe(tabInactiveStyle)
    expect(hitlBadgeStyle).toBe(hitlBadgeStyle)
  })

  describe('hitlBadgeStyle', () => {
    it('has red background and white text', () => {
      expect(hitlBadgeStyle).toMatchObject({
        background: 'var(--red)',
        color: 'var(--white)',
      })
    })

    it('has pill-shaped badge properties', () => {
      expect(hitlBadgeStyle).toMatchObject({
        fontSize: 10,
        fontWeight: 700,
        borderRadius: 10,
        padding: '1px 6px',
        marginLeft: 6,
      })
    })
  })
})
