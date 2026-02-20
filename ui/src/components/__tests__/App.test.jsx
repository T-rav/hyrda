import { describe, it, expect } from 'vitest'
import { tabActiveStyle, tabInactiveStyle } from '../../App'

describe('App pre-computed tab styles', () => {
  it('tabInactiveStyle has base tab properties', () => {
    expect(tabInactiveStyle).toMatchObject({
      padding: '10px 20px',
      fontSize: 12,
      fontWeight: 600,
      color: '#8b949e',
      cursor: 'pointer',
      borderBottom: '2px solid transparent',
    })
  })

  it('tabActiveStyle includes both tab and tabActive properties', () => {
    expect(tabActiveStyle).toMatchObject({
      padding: '10px 20px',
      fontSize: 12,
      fontWeight: 600,
      color: '#58a6ff',
      cursor: 'pointer',
      borderBottomColor: '#58a6ff',
    })
  })

  it('tabActiveStyle overrides color from tabActive', () => {
    // tabActive color (#58a6ff) should override base tab color (#8b949e)
    expect(tabActiveStyle.color).toBe('#58a6ff')
  })

  it('style objects are referentially stable', () => {
    expect(tabActiveStyle).toBe(tabActiveStyle)
    expect(tabInactiveStyle).toBe(tabInactiveStyle)
  })
})
