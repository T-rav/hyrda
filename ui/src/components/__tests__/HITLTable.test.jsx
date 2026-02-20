import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { HITLTable } from '../HITLTable'

describe('HITLTable', () => {
  it('renders "No stuck PRs" when items is empty array', () => {
    render(<HITLTable items={[]} onRefresh={() => {}} />)
    expect(screen.getByText('No stuck PRs')).toBeInTheDocument()
  })

  it('renders items passed via props', () => {
    const items = [
      { issue: 10, title: 'Bug fix', issueUrl: 'https://github.com/r/issues/10', pr: 20, prUrl: 'https://github.com/r/pull/20', branch: 'agent/issue-10' },
      { issue: 11, title: 'Feature', issueUrl: 'https://github.com/r/issues/11', pr: 0, prUrl: '', branch: 'agent/issue-11' },
    ]
    render(<HITLTable items={items} onRefresh={() => {}} />)
    expect(screen.getByText('#10')).toBeInTheDocument()
    expect(screen.getByText('Bug fix')).toBeInTheDocument()
    expect(screen.getByText('#20')).toBeInTheDocument()
    expect(screen.getByText('#11')).toBeInTheDocument()
    expect(screen.getByText('Feature')).toBeInTheDocument()
    expect(screen.getByText('No PR')).toBeInTheDocument()
  })

  it('shows correct count in header', () => {
    const items = [
      { issue: 10, title: 'Bug', issueUrl: '', pr: 20, prUrl: '', branch: 'b1' },
      { issue: 11, title: 'Feat', issueUrl: '', pr: 21, prUrl: '', branch: 'b2' },
    ]
    render(<HITLTable items={items} onRefresh={() => {}} />)
    expect(screen.getByText('2 issues stuck on CI')).toBeInTheDocument()
  })

  it('shows singular when one item', () => {
    const items = [
      { issue: 10, title: 'Bug', issueUrl: '', pr: 20, prUrl: '', branch: 'b1' },
    ]
    render(<HITLTable items={items} onRefresh={() => {}} />)
    expect(screen.getByText('1 issue stuck on CI')).toBeInTheDocument()
  })

  it('refresh button calls onRefresh prop', () => {
    const onRefresh = vi.fn()
    const items = [
      { issue: 10, title: 'Bug', issueUrl: '', pr: 20, prUrl: '', branch: 'b1' },
    ]
    render(<HITLTable items={items} onRefresh={onRefresh} />)
    fireEvent.click(screen.getByText('Refresh'))
    expect(onRefresh).toHaveBeenCalledOnce()
  })

  it('does not fetch data on mount (no side effects)', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    render(<HITLTable items={[]} onRefresh={() => {}} />)
    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })
})
