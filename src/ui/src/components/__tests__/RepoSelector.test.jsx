import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

const mockUseHydraFlow = vi.fn()

vi.mock('../../context/HydraFlowContext', () => ({
  useHydraFlow: (...args) => mockUseHydraFlow(...args),
}))

const { RepoSelector } = await import('../RepoSelector')

function makeContext(overrides = {}) {
  return {
    supervisedRepos: [],
    runtimes: [],
    selectedRepoSlug: null,
    selectRepo: vi.fn(),
    ...overrides,
  }
}

describe('RepoSelector', () => {
  beforeEach(() => {
    mockUseHydraFlow.mockReturnValue(makeContext())
  })

  it('shows All repos label when no repo is selected', () => {
    render(<RepoSelector />)
    expect(screen.getByText('All repos')).toBeInTheDocument()
  })

  it('renders options and selects repo', () => {
    const selectRepo = vi.fn()
    mockUseHydraFlow.mockReturnValue(makeContext({
      supervisedRepos: [{ slug: 'acme/app', path: '/repos/acme/app', running: true }],
      selectRepo,
    }))
    render(<RepoSelector />)
    fireEvent.click(screen.getByTestId('repo-selector-trigger'))
    fireEvent.click(screen.getByText('acme/app'))
    expect(selectRepo).toHaveBeenCalledWith('acme/app')
  })

  it('opens register dialog when clicking register button', () => {
    const onOpenRegister = vi.fn()
    render(<RepoSelector onOpenRegister={onOpenRegister} />)
    fireEvent.click(screen.getByTestId('repo-selector-trigger'))
    fireEvent.click(screen.getByText('+ Register repo'))
    expect(onOpenRegister).toHaveBeenCalledTimes(1)
  })
})
