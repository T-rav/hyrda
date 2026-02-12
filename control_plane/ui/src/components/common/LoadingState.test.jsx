import React from 'react'
import { render, screen } from '@testing-library/react'
import LoadingState from './LoadingState'

describe('LoadingState', () => {
  describe('rendering', () => {
    it('renders default message', () => {
      render(<LoadingState />)
      expect(screen.getByText('Loading...')).toBeInTheDocument()
    })

    it('renders custom message', () => {
      render(<LoadingState message="Fetching agents..." />)
      expect(screen.getByText('Fetching agents...')).toBeInTheDocument()
    })

    it('renders without message when message is empty', () => {
      render(<LoadingState message="" />)
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
    })

    it('applies default loading-state class', () => {
      render(<LoadingState />)
      expect(document.querySelector('.loading-state')).toBeInTheDocument()
    })

    it('applies custom className', () => {
      render(<LoadingState className="custom-loading" />)
      expect(document.querySelector('.loading-state')).toHaveClass('custom-loading')
    })
  })

  describe('sizes', () => {
    it('applies centered class by default', () => {
      render(<LoadingState />)
      expect(document.querySelector('.loading-state')).toHaveClass('loading-state-centered')
    })

    it('does not apply centered class when centered is false', () => {
      render(<LoadingState centered={false} />)
      expect(document.querySelector('.loading-state')).not.toHaveClass('loading-state-centered')
    })

    it('renders spinner icon', () => {
      render(<LoadingState />)
      expect(document.querySelector('.loading-state-spinner')).toBeInTheDocument()
    })
  })

  describe('fullscreen mode', () => {
    it('does not apply fullscreen class by default', () => {
      render(<LoadingState />)
      expect(document.querySelector('.loading-state')).not.toHaveClass('loading-state-fullscreen')
    })

    it('applies fullscreen class when fullscreen is true', () => {
      render(<LoadingState fullscreen />)
      expect(document.querySelector('.loading-state')).toHaveClass('loading-state-fullscreen')
    })

    it('renders content wrapper in fullscreen mode', () => {
      render(<LoadingState fullscreen />)
      expect(document.querySelector('.loading-state-content')).toBeInTheDocument()
    })
  })

  describe('accessibility', () => {
    it('has status role', () => {
      render(<LoadingState />)
      expect(screen.getByRole('status')).toBeInTheDocument()
    })

    it('has aria-live polite', () => {
      render(<LoadingState />)
      expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
    })

    it('spinner is hidden from screen readers', () => {
      render(<LoadingState />)
      expect(document.querySelector('.loading-state-spinner')).toHaveAttribute('aria-hidden', 'true')
    })
  })

  describe('structure', () => {
    it('renders message with correct class', () => {
      render(<LoadingState message="Loading..." />)
      expect(screen.getByText('Loading...')).toHaveClass('loading-state-message')
    })
  })
})
