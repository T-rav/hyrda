import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { Plus, Trash2 } from 'lucide-react'
import Button from './Button'

describe('Button', () => {
  describe('rendering', () => {
    it('renders children correctly', () => {
      render(<Button>Click me</Button>)
      expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument()
    })

    it('renders with default type="button"', () => {
      render(<Button>Test</Button>)
      expect(screen.getByRole('button')).toHaveAttribute('type', 'button')
    })

    it('renders with type="submit" when specified', () => {
      render(<Button type="submit">Submit</Button>)
      expect(screen.getByRole('button')).toHaveAttribute('type', 'submit')
    })

    it('applies custom className', () => {
      render(<Button className="custom-class">Test</Button>)
      expect(screen.getByRole('button')).toHaveClass('custom-class')
    })

    it('renders left icon', () => {
      render(<Button leftIcon={<Plus data-testid="left-icon" />}>Test</Button>)
      expect(screen.getByTestId('left-icon')).toBeInTheDocument()
    })

    it('renders right icon', () => {
      render(<Button rightIcon={<Trash2 data-testid="right-icon" />}>Test</Button>)
      expect(screen.getByTestId('right-icon')).toBeInTheDocument()
    })

    it('renders with aria-label', () => {
      render(<Button ariaLabel="Close dialog">X</Button>)
      expect(screen.getByRole('button', { name: 'Close dialog' })).toBeInTheDocument()
    })

    it('renders with title attribute', () => {
      render(<Button title="Click to save">Save</Button>)
      expect(screen.getByRole('button')).toHaveAttribute('title', 'Click to save')
    })
  })

  describe('variants', () => {
    it('applies primary variant class by default', () => {
      render(<Button>Test</Button>)
      expect(screen.getByRole('button')).toHaveClass('btn-primary')
    })

    it('applies secondary variant class', () => {
      render(<Button variant="secondary">Test</Button>)
      expect(screen.getByRole('button')).toHaveClass('btn-secondary')
    })

    it('applies danger variant class', () => {
      render(<Button variant="danger">Test</Button>)
      expect(screen.getByRole('button')).toHaveClass('btn-danger')
    })

    it('applies success variant class', () => {
      render(<Button variant="success">Test</Button>)
      expect(screen.getByRole('button')).toHaveClass('btn-success')
    })

    it('applies ghost variant class', () => {
      render(<Button variant="ghost">Test</Button>)
      expect(screen.getByRole('button')).toHaveClass('btn-ghost')
    })

    it('applies link variant class', () => {
      render(<Button variant="link">Test</Button>)
      expect(screen.getByRole('button')).toHaveClass('btn-link')
    })
  })

  describe('sizes', () => {
    it('does not apply size class for md by default', () => {
      render(<Button>Test</Button>)
      const button = screen.getByRole('button')
      expect(button).not.toHaveClass('btn-sm')
      expect(button).not.toHaveClass('btn-lg')
    })

    it('applies sm size class', () => {
      render(<Button size="sm">Test</Button>)
      expect(screen.getByRole('button')).toHaveClass('btn-sm')
    })

    it('applies lg size class', () => {
      render(<Button size="lg">Test</Button>)
      expect(screen.getByRole('button')).toHaveClass('btn-lg')
    })
  })

  describe('loading state', () => {
    it('shows loading spinner when isLoading is true', () => {
      render(<Button isLoading>Loading</Button>)
      expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'true')
    })

    it('disables button when isLoading is true', () => {
      render(<Button isLoading>Loading</Button>)
      expect(screen.getByRole('button')).toBeDisabled()
    })

    it('hides icons when loading', () => {
      render(
        <Button isLoading leftIcon={<Plus data-testid="left-icon" />}>
          Loading
        </Button>
      )
      expect(screen.queryByTestId('left-icon')).not.toBeInTheDocument()
    })

    it('applies loading class when isLoading', () => {
      render(<Button isLoading>Loading</Button>)
      expect(screen.getByRole('button')).toHaveClass('btn-loading')
    })
  })

  describe('disabled state', () => {
    it('disables button when disabled is true', () => {
      render(<Button disabled>Disabled</Button>)
      expect(screen.getByRole('button')).toBeDisabled()
    })

    it('does not disable button by default', () => {
      render(<Button>Enabled</Button>)
      expect(screen.getByRole('button')).not.toBeDisabled()
    })
  })

  describe('interactions', () => {
    it('calls onClick handler when clicked', () => {
      const handleClick = jest.fn()
      render(<Button onClick={handleClick}>Click me</Button>)
      fireEvent.click(screen.getByRole('button'))
      expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('does not call onClick when disabled', () => {
      const handleClick = jest.fn()
      render(<Button onClick={handleClick} disabled>Disabled</Button>)
      fireEvent.click(screen.getByRole('button'))
      expect(handleClick).not.toHaveBeenCalled()
    })

    it('does not call onClick when loading', () => {
      const handleClick = jest.fn()
      render(<Button onClick={handleClick} isLoading>Loading</Button>)
      fireEvent.click(screen.getByRole('button'))
      expect(handleClick).not.toHaveBeenCalled()
    })
  })

  describe('accessibility', () => {
    it('has correct button role', () => {
      render(<Button>Test</Button>)
      expect(screen.getByRole('button')).toBeInTheDocument()
    })

    it('sets aria-busy correctly when not loading', () => {
      render(<Button>Test</Button>)
      expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'false')
    })

    it('hides icons from screen readers', () => {
      render(<Button leftIcon={<Plus data-testid="icon" />}>Test</Button>)
      const icon = screen.getByTestId('icon').parentElement
      expect(icon).toHaveAttribute('aria-hidden', 'true')
    })
  })
})
