import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import Modal from './Modal'

describe('Modal', () => {
  const mockOnClose = jest.fn()
  const mockOnConfirm = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
    // Reset body overflow
    document.body.style.overflow = ''
  })

  describe('rendering', () => {
    it('does not render when isOpen is false', () => {
      render(
        <Modal isOpen={false} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('renders when isOpen is true', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('renders title correctly', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      expect(screen.getByText('Test Modal')).toBeInTheDocument()
    })

    it('renders children content', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          <p>Modal content here</p>
        </Modal>
      )
      expect(screen.getByText('Modal content here')).toBeInTheDocument()
    })

    it('renders close button by default', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      expect(screen.getByLabelText('Close modal')).toBeInTheDocument()
    })

    it('hides close button when showCloseButton is false', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal" showCloseButton={false}>
          Content
        </Modal>
      )
      expect(screen.queryByLabelText('Close modal')).not.toBeInTheDocument()
    })

    it('applies size class correctly', () => {
      const { rerender } = render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" size="sm">
          Content
        </Modal>
      )
      expect(document.querySelector('.modal-content')).toHaveClass('modal-sm')

      rerender(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" size="lg">
          Content
        </Modal>
      )
      expect(document.querySelector('.modal-content')).toHaveClass('modal-lg')
    })

    it('applies custom className to content', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" className="custom-modal">
          Content
        </Modal>
      )
      expect(document.querySelector('.modal-content')).toHaveClass('custom-modal')
    })
  })

  describe('default footer', () => {
    it('renders default footer with confirm and cancel buttons', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" onConfirm={mockOnConfirm}>
          Content
        </Modal>
      )
      expect(screen.getByText('Cancel')).toBeInTheDocument()
      expect(screen.getByText('Confirm')).toBeInTheDocument()
    })

    it('does not render default footer when onConfirm is not provided', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test">
          Content
        </Modal>
      )
      expect(screen.queryByText('Cancel')).not.toBeInTheDocument()
      expect(screen.queryByText('Confirm')).not.toBeInTheDocument()
    })

    it('hides default footer when hideDefaultFooter is true', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" onConfirm={mockOnConfirm} hideDefaultFooter={true}>
          Content
        </Modal>
      )
      expect(screen.queryByText('Cancel')).not.toBeInTheDocument()
      expect(screen.queryByText('Confirm')).not.toBeInTheDocument()
    })

    it('renders custom footer when provided', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" footer={<button>Custom Action</button>}>
          Content
        </Modal>
      )
      expect(screen.getByText('Custom Action')).toBeInTheDocument()
    })

    it('calls onConfirm when confirm button is clicked', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" onConfirm={mockOnConfirm}>
          Content
        </Modal>
      )
      fireEvent.click(screen.getByText('Confirm'))
      expect(mockOnConfirm).toHaveBeenCalledTimes(1)
    })

    it('calls onClose when cancel button is clicked', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" onConfirm={mockOnConfirm}>
          Content
        </Modal>
      )
      fireEvent.click(screen.getByText('Cancel'))
      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })

    it('uses custom confirm and cancel text', () => {
      render(
        <Modal
          isOpen={true}
          onClose={mockOnClose}
          title="Test"
          onConfirm={mockOnConfirm}
          confirmText="Save"
          cancelText="Discard"
        >
          Content
        </Modal>
      )
      expect(screen.getByText('Save')).toBeInTheDocument()
      expect(screen.getByText('Discard')).toBeInTheDocument()
    })

    it('shows loading state on confirm button when isLoading is true', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" onConfirm={mockOnConfirm} isLoading={true}>
          Content
        </Modal>
      )
      expect(screen.getByRole('button', { name: /confirm/i })).toHaveAttribute('aria-busy', 'true')
      expect(screen.getByRole('button', { name: /confirm/i })).toBeDisabled()
    })
  })

  describe('close interactions', () => {
    it('calls onClose when close button is clicked', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      fireEvent.click(screen.getByLabelText('Close modal'))
      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })

    it('calls onClose when overlay is clicked by default', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      fireEvent.click(screen.getByRole('dialog'))
      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })

    it('does not call onClose when overlay click is disabled', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal" closeOnOverlayClick={false}>
          Content
        </Modal>
      )
      fireEvent.click(screen.getByRole('dialog'))
      expect(mockOnClose).not.toHaveBeenCalled()
    })

    it('calls onClose when Escape key is pressed by default', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      fireEvent.keyDown(document, { key: 'Escape' })
      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })

    it('does not call onClose when Escape is disabled', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal" closeOnEsc={false}>
          Content
        </Modal>
      )
      fireEvent.keyDown(document, { key: 'Escape' })
      expect(mockOnClose).not.toHaveBeenCalled()
    })

    it('does not call onClose when clicking modal content', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          <button>Inside button</button>
        </Modal>
      )
      fireEvent.click(screen.getByText('Inside button'))
      expect(mockOnClose).not.toHaveBeenCalled()
    })
  })

  describe('accessibility', () => {
    it('has correct dialog role', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('has aria-modal attribute', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true')
    })

    it('associates title with aria-labelledby', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      const dialog = screen.getByRole('dialog')
      const title = screen.getByText('Test Modal')
      expect(title).toHaveAttribute('id', 'modal-title')
      expect(dialog).toHaveAttribute('aria-labelledby', 'modal-title')
    })

    it('has content region with label', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      expect(screen.getByRole('region', { name: 'Modal content' })).toBeInTheDocument()
    })

    it('modal content is focusable', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      const content = document.querySelector('.modal-content')
      expect(content).toHaveAttribute('tabIndex', '-1')
    })
  })

  describe('body scroll lock', () => {
    it('locks body scroll when open', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      expect(document.body.style.overflow).toBe('hidden')
    })

    it('restores body scroll when closed', () => {
      const { rerender } = render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      expect(document.body.style.overflow).toBe('hidden')

      rerender(
        <Modal isOpen={false} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      expect(document.body.style.overflow).toBe('')
    })

    it('cleans up body scroll on unmount', () => {
      const { unmount } = render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      )
      unmount()
      expect(document.body.style.overflow).toBe('')
    })
  })
})
