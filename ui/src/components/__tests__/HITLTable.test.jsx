import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { HITLTable } from '../HITLTable'

const MOCK_ITEMS = [
  { issue: 1, title: 'Bug A', pr: 10, branch: 'fix-a', issueUrl: '#', prUrl: '#' },
  { issue: 2, title: 'Bug B', pr: 0, branch: 'fix-b', issueUrl: '#', prUrl: '' },
  { issue: 3, title: 'Bug C', pr: 12, branch: 'fix-c', issueUrl: '#', prUrl: '#' },
]

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('HITLTable onCountChange callback', () => {
  it('calls onCountChange with item count after successful fetch', async () => {
    const onCountChange = vi.fn()
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(MOCK_ITEMS),
    })

    render(<HITLTable onCountChange={onCountChange} />)

    await waitFor(() => {
      expect(onCountChange).toHaveBeenCalledWith(3)
    })
  })

  it('calls onCountChange with 0 on fetch error', async () => {
    const onCountChange = vi.fn()
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'))

    render(<HITLTable onCountChange={onCountChange} />)

    await waitFor(() => {
      expect(onCountChange).toHaveBeenCalledWith(0)
    })
  })

  it('renders without errors when onCountChange is not provided', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(MOCK_ITEMS),
    })

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByText('3 issues stuck on CI')).toBeInTheDocument()
    })
  })

  it('renders fetched items in the table', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(MOCK_ITEMS),
    })

    render(<HITLTable onCountChange={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('Bug A')).toBeInTheDocument()
      expect(screen.getByText('Bug B')).toBeInTheDocument()
      expect(screen.getByText('Bug C')).toBeInTheDocument()
    })
  })
})
