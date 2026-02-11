import React from 'react'
import { render, screen } from '@testing-library/react'
import { Check, X } from 'lucide-react'
import Badge from './Badge'

describe('Badge', () => {
  describe('rendering', () => {
    it('renders children correctly', () => {
      render(<Badge>Active</Badge>)
      expect(screen.getByText('Active')).toBeInTheDocument()
    })

    it('applies default badge class', () => {
      render(<Badge>Test</Badge>)
      expect(document.querySelector('.badge')).toBeInTheDocument()
    })

    it('renders left icon', () => {
      render(<Badge leftIcon={<Check data-testid="check-icon" />}>Success</Badge>)
      expect(screen.getByTestId('check-icon')).toBeInTheDocument()
    })

    it('renders right icon', () => {
      render(<Badge rightIcon={<X data-testid="x-icon" />}>Remove</Badge>)
      expect(screen.getByTestId('x-icon')).toBeInTheDocument()
    })

    it('applies custom className', () => {
      render(<Badge className="custom-badge">Test</Badge>)
      expect(document.querySelector('.badge')).toHaveClass('custom-badge')
    })
  })

  describe('variants', () => {
    it('applies primary variant class', () => {
      render(<Badge variant="primary">Test</Badge>)
      expect(document.querySelector('.badge')).toHaveClass('badge-primary')
    })

    it('applies secondary variant class', () => {
      render(<Badge variant="secondary">Test</Badge>)
      expect(document.querySelector('.badge')).toHaveClass('badge-secondary')
    })

    it('applies success variant class', () => {
      render(<Badge variant="success">Test</Badge>)
      expect(document.querySelector('.badge')).toHaveClass('badge-success')
    })

    it('applies danger variant class', () => {
      render(<Badge variant="danger">Test</Badge>)
      expect(document.querySelector('.badge')).toHaveClass('badge-danger')
    })

    it('applies warning variant class', () => {
      render(<Badge variant="warning">Test</Badge>)
      expect(document.querySelector('.badge')).toHaveClass('badge-warning')
    })

    it('applies info variant class', () => {
      render(<Badge variant="info">Test</Badge>)
      expect(document.querySelector('.badge')).toHaveClass('badge-info')
    })

    it('applies outline variant class', () => {
      render(<Badge variant="outline">Test</Badge>)
      expect(document.querySelector('.badge')).toHaveClass('badge-outline')
    })
  })

  describe('sizes', () => {
    it('does not apply size class for md by default', () => {
      render(<Badge>Test</Badge>)
      const badge = document.querySelector('.badge')
      expect(badge).not.toHaveClass('badge-sm')
      expect(badge).not.toHaveClass('badge-lg')
    })

    it('applies sm size class', () => {
      render(<Badge size="sm">Test</Badge>)
      expect(document.querySelector('.badge')).toHaveClass('badge-sm')
    })

    it('applies lg size class', () => {
      render(<Badge size="lg">Test</Badge>)
      expect(document.querySelector('.badge')).toHaveClass('badge-lg')
    })
  })

  describe('structure', () => {
    it('wraps text in badge-text span', () => {
      render(<Badge>Test</Badge>)
      const textElement = screen.getByText('Test')
      expect(textElement).toHaveClass('badge-text')
    })

    it('hides icons from screen readers', () => {
      render(<Badge leftIcon={<Check data-testid="icon" />}>Test</Badge>)
      const icon = screen.getByTestId('icon').parentElement
      expect(icon).toHaveAttribute('aria-hidden', 'true')
    })
  })
})
