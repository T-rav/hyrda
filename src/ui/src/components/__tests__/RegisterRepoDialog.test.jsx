import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const mockUseHydraFlow = vi.fn()

vi.mock('../../context/HydraFlowContext', () => ({
  useHydraFlow: (...args) => mockUseHydraFlow(...args),
}))

const { RegisterRepoDialog } = await import('../RegisterRepoDialog')

describe('RegisterRepoDialog', () => {
  beforeEach(() => {
    mockUseHydraFlow.mockReturnValue({
      addRepoBySlug: vi.fn().mockResolvedValue({ ok: true }),
      addRepoByPath: vi.fn().mockResolvedValue({ ok: true }),
    })
  })

  it('does not render when closed', () => {
    const { container } = render(<RegisterRepoDialog isOpen={false} onClose={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('validates when no inputs provided', () => {
    render(<RegisterRepoDialog isOpen onClose={() => {}} />)
    fireEvent.submit(screen.getByTestId('register-submit').closest('form'))
    expect(screen.getByText('Enter a GitHub slug or repo path')).toBeInTheDocument()
  })

  it('submits slug via addRepoBySlug', async () => {
    const addRepoBySlug = vi.fn().mockResolvedValue({ ok: true })
    mockUseHydraFlow.mockReturnValue({
      addRepoBySlug,
      addRepoByPath: vi.fn(),
    })
    const onClose = vi.fn()
    render(<RegisterRepoDialog isOpen onClose={onClose} />)
    fireEvent.change(screen.getByLabelText('GitHub slug'), { target: { value: 'acme/app' } })
    fireEvent.click(screen.getByTestId('register-submit'))
    await waitFor(() => expect(addRepoBySlug).toHaveBeenCalledWith('acme/app'))
    expect(onClose).toHaveBeenCalled()
  })

  it('falls back to path registration when slug is empty', async () => {
    const addRepoByPath = vi.fn().mockResolvedValue({ ok: true })
    mockUseHydraFlow.mockReturnValue({
      addRepoBySlug: vi.fn(),
      addRepoByPath,
    })
    render(<RegisterRepoDialog isOpen onClose={() => {}} />)
    fireEvent.change(screen.getByLabelText('Filesystem path'), { target: { value: '/repos/demo' } })
    fireEvent.click(screen.getByTestId('register-submit'))
    await waitFor(() => expect(addRepoByPath).toHaveBeenCalledWith('/repos/demo'))
  })

  it('displays error message when registration fails', async () => {
    const addRepoBySlug = vi.fn().mockResolvedValue({ ok: false, error: 'Repo not found' })
    mockUseHydraFlow.mockReturnValue({
      addRepoBySlug,
      addRepoByPath: vi.fn(),
    })
    const onClose = vi.fn()
    render(<RegisterRepoDialog isOpen onClose={onClose} />)
    fireEvent.change(screen.getByLabelText('GitHub slug'), { target: { value: 'acme/missing' } })
    fireEvent.click(screen.getByTestId('register-submit'))
    await waitFor(() => expect(screen.getByText('Repo not found')).toBeInTheDocument())
    expect(onClose).not.toHaveBeenCalled()
  })
})
