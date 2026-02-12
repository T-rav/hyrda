import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { FolderOpen } from 'lucide-react'
import EmptyState from './EmptyState'

describe('EmptyState', () => {
  describe('rendering', () => {
    it('renders default title', () => {
      render(<EmptyState />)
      expect(screen.getByText('No items found')).toBeInTheDocument()
    })

    it('renders custom title', () => {
      render(<EmptyState title="No agents available" />)
      expect(screen.getByText('No agents available')).toBeInTheDocument()
    })

    it('renders description when provided', () => {
      render(<EmptyState description="Try creating a new agent to get started" />)
      expect(screen.getByText('Try creating a new agent to get started')).toBeInTheDocument()
    })

    it('renders default icon (Inbox)', () => {
      render(<EmptyState />)
      expect(document.querySelector('.empty-state-icon')).toBeInTheDocument()
    })

    it('renders custom icon', () => {
      render(<EmptyState icon={<FolderOpen data-testid="folder-icon" />} />)
      expect(screen.getByTestId('folder-icon')).toBeInTheDocument()
    })

    it('applies custom className', () => {
      render(<EmptyState className="custom-empty" />)
      expect(document.querySelector('.empty-state-container')).toHaveClass('custom-empty')
    })
  })

  describe('action button', () => {
    it('does not render action button when actionLabel is not provided', () => {
      render(<EmptyState />)
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })

    it('does not render action button when onAction is not provided', () => {
      render(<EmptyState actionLabel="Create" />)
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })

    it('renders action button when both actionLabel and onAction are provided', () => {
      render(<EmptyState actionLabel="Create New" onAction={() => {}} />)
      expect(screen.getByRole('button', { name: 'Create New' })).toBeInTheDocument()
    })

    it('calls onAction when action button is clicked', () => {
      const handleAction = jest.fn()
      render(<EmptyState actionLabel="Create" onAction={handleAction} />)
      fireEvent.click(screen.getByRole('button', { name: 'Create' }))
      expect(handleAction).toHaveBeenCalledTimes(1)
    })

    it('uses primary variant for action button by default', () => {
      render(<EmptyState actionLabel="Create" onAction={() => {}} />)
      expect(screen.getByRole('button')).toHaveClass('btn-primary')
    })

    it('uses custom variant for action button when specified', () => {
      render(<EmptyState actionLabel="Create" onAction={() => {}} actionVariant="success" />)
      expect(screen.getByRole('button')).toHaveClass('btn-success')
    })
  })

  describe('structure', () => {
    it('renders icon container with correct class', () => {
      render(<EmptyState />)
      expect(document.querySelector('.empty-state-icon')).toBeInTheDocument()
    })

    it('icon is hidden from screen readers', () => {
      render(<EmptyState />)
      expect(document.querySelector('.empty-state-icon')).toHaveAttribute('aria-hidden', 'true')
    })

    it('renders title with correct class', () => {
      render(<EmptyState title="Test" />)
      expect(screen.getByText('Test')).toHaveClass('empty-state-title')
    })

    it('renders description with correct class', () => {
      render(<EmptyState description="Test description" />)
      expect(screen.getByText('Test description')).toHaveClass('empty-state-description')
    })

    it('renders action container with correct class', () => {
      render(<EmptyState actionLabel="Create" onAction={() => {}} />)
      expect(document.querySelector('.empty-state-action')).toBeInTheDocument()
    })

    it('title has correct heading element', () => {
      render(<EmptyState title="Test Title" />)
      expect(screen.getByText('Test Title').tagName).toBe('H3')
    })
  })
})
