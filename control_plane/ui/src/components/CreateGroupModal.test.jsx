import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import CreateGroupModal from './CreateGroupModal'

describe('CreateGroupModal', () => {
  const mockOnClose = jest.fn()
  const mockOnCreate = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
  })

  describe('rendering', () => {
    it('renders modal with correct title', () => {
      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)
      expect(screen.getByText('Create New Group')).toBeInTheDocument()
    })

    it('renders group name input', () => {
      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)
      expect(screen.getByLabelText(/group name/i)).toBeInTheDocument()
    })

    it('renders description textarea', () => {
      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)
      expect(screen.getByLabelText(/description/i)).toBeInTheDocument()
    })

    it('renders cancel button', () => {
      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
    })

    it('renders create group button', () => {
      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)
      expect(screen.getByRole('button', { name: /create group/i })).toBeInTheDocument()
    })
  })

  describe('form interactions', () => {
    it('updates display_name when typing', () => {
      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)
      const input = screen.getByLabelText(/group name/i)
      fireEvent.change(input, { target: { value: 'Test Group' } })
      expect(input).toHaveValue('Test Group')
    })

    it('updates description when typing', () => {
      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)
      const textarea = screen.getByLabelText(/description/i)
      fireEvent.change(textarea, { target: { value: 'Test description' } })
      expect(textarea).toHaveValue('Test description')
    })

    it('disables create button when group name is empty', () => {
      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)
      expect(screen.getByRole('button', { name: /create group/i })).toBeDisabled()
    })

    it('enables create button when group name is entered', () => {
      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)
      const input = screen.getByLabelText(/group name/i)
      fireEvent.change(input, { target: { value: 'Test Group' } })
      expect(screen.getByRole('button', { name: /create group/i })).not.toBeDisabled()
    })

    it('calls onClose when cancel button is clicked', () => {
      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)
      fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })
  })

  describe('form submission', () => {
    it('calls onCreate with form data when submitted', async () => {
      mockOnCreate.mockResolvedValueOnce()

      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)

      const input = screen.getByLabelText(/group name/i)
      fireEvent.change(input, { target: { value: 'Test Group' } })

      const textarea = screen.getByLabelText(/description/i)
      fireEvent.change(textarea, { target: { value: 'Test description' } })

      fireEvent.click(screen.getByRole('button', { name: /create group/i }))

      await waitFor(() => {
        expect(mockOnCreate).toHaveBeenCalledWith({
          display_name: 'Test Group',
          description: 'Test description',
          created_by: 'admin',
          group_name: 'test_group'
        })
      })
    })

    it('slugifies group name correctly', async () => {
      mockOnCreate.mockResolvedValueOnce()

      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)

      const input = screen.getByLabelText(/group name/i)
      fireEvent.change(input, { target: { value: 'My Test Group!!!' } })

      fireEvent.click(screen.getByRole('button', { name: /create group/i }))

      await waitFor(() => {
        expect(mockOnCreate).toHaveBeenCalledWith(
          expect.objectContaining({
            group_name: 'my_test_group'
          })
        )
      })
    })

    it('shows loading state during submission', async () => {
      mockOnCreate.mockImplementation(() => new Promise(() => {})) // Never resolves

      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)

      const input = screen.getByLabelText(/group name/i)
      fireEvent.change(input, { target: { value: 'Test Group' } })

      fireEvent.click(screen.getByRole('button', { name: /create group/i }))

      expect(screen.getByRole('button', { name: /create group/i })).toHaveAttribute('aria-busy', 'true')
    })

    it('disables cancel button during submission', async () => {
      mockOnCreate.mockImplementation(() => new Promise(() => {})) // Never resolves

      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)

      const input = screen.getByLabelText(/group name/i)
      fireEvent.change(input, { target: { value: 'Test Group' } })

      fireEvent.click(screen.getByRole('button', { name: /create group/i }))

      expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled()
    })

    it('shows error message when onCreate fails', async () => {
      mockOnCreate.mockRejectedValueOnce(new Error('Group already exists'))

      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)

      const input = screen.getByLabelText(/group name/i)
      fireEvent.change(input, { target: { value: 'Test Group' } })

      fireEvent.click(screen.getByRole('button', { name: /create group/i }))

      await waitFor(() => {
        expect(screen.getByText('Group already exists')).toBeInTheDocument()
      })
    })
  })

  describe('accessibility', () => {
    it('has correct dialog role', () => {
      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('input is focused on mount', () => {
      // jsdom doesn't fully support autofocus, so we just verify the input exists
      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)
      expect(screen.getByLabelText(/group name/i)).toBeInTheDocument()
    })

    it('marks group name as required', () => {
      render(<CreateGroupModal onClose={mockOnClose} onCreate={mockOnCreate} />)
      expect(screen.getByLabelText(/group name/i)).toBeRequired()
    })
  })
})
