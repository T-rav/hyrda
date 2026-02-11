import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import Card from './Card'

describe('Card', () => {
  describe('rendering', () => {
    it('renders children correctly', () => {
      render(
        <Card>
          <p>Card content</p>
        </Card>
      )
      expect(screen.getByText('Card content')).toBeInTheDocument()
    })

    it('applies default card class', () => {
      render(<Card>Test</Card>)
      expect(document.querySelector('.card')).toBeInTheDocument()
    })

    it('renders title in header', () => {
      render(<Card title="Card Title">Content</Card>)
      expect(screen.getByText('Card Title')).toBeInTheDocument()
    })

    it('renders custom header content', () => {
      render(
        <Card header={<button>Custom Header</button>}>
          Content
        </Card>
      )
      expect(screen.getByText('Custom Header')).toBeInTheDocument()
    })

    it('renders footer content', () => {
      render(
        <Card footer={<button>Footer Button</button>}>
          Content
        </Card>
      )
      expect(screen.getByText('Footer Button')).toBeInTheDocument()
    })

    it('applies outlined variant class', () => {
      render(<Card variant="outlined">Test</Card>)
      expect(document.querySelector('.card')).toHaveClass('card-outlined')
    })

    it('applies ghost variant class', () => {
      render(<Card variant="ghost">Test</Card>)
      expect(document.querySelector('.card')).toHaveClass('card-ghost')
    })

    it('applies custom className', () => {
      render(<Card className="custom-card">Test</Card>)
      expect(document.querySelector('.card')).toHaveClass('custom-card')
    })

    it('applies hoverable class', () => {
      render(<Card hoverable>Test</Card>)
      expect(document.querySelector('.card')).toHaveClass('card-hoverable')
    })
  })

  describe('interactions', () => {
    it('calls onClick when clicked', () => {
      const handleClick = jest.fn()
      render(<Card onClick={handleClick}>Clickable Card</Card>)
      fireEvent.click(screen.getByRole('button'))
      expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('has button role when onClick is provided', () => {
      render(<Card onClick={() => {}}>Clickable</Card>)
      expect(screen.getByRole('button')).toBeInTheDocument()
    })

    it('has tabIndex when onClick is provided', () => {
      render(<Card onClick={() => {}}>Clickable</Card>)
      expect(screen.getByRole('button')).toHaveAttribute('tabIndex', '0')
    })

    it('applies clickable class when onClick is provided', () => {
      render(<Card onClick={() => {}}>Clickable</Card>)
      expect(document.querySelector('.card')).toHaveClass('card-clickable')
    })

    it('applies clickable class when clickable prop is true', () => {
      render(<Card clickable>Clickable</Card>)
      expect(document.querySelector('.card')).toHaveClass('card-clickable')
    })
  })

  describe('structure', () => {
    it('renders header when title is provided', () => {
      render(<Card title="Title">Content</Card>)
      expect(document.querySelector('.card-header')).toBeInTheDocument()
    })

    it('does not render header when no title or header prop', () => {
      render(<Card>Content</Card>)
      expect(document.querySelector('.card-header')).not.toBeInTheDocument()
    })

    it('renders body with card-body class', () => {
      render(<Card>Content</Card>)
      expect(document.querySelector('.card-body')).toBeInTheDocument()
    })

    it('renders footer when footer prop is provided', () => {
      render(<Card footer={<span>Footer</span>}>Content</Card>)
      expect(document.querySelector('.card-footer')).toBeInTheDocument()
    })

    it('does not render footer when no footer prop', () => {
      render(<Card>Content</Card>)
      expect(document.querySelector('.card-footer')).not.toBeInTheDocument()
    })

    it('title has correct heading element', () => {
      render(<Card title="Card Title">Content</Card>)
      expect(screen.getByText('Card Title').tagName).toBe('H3')
    })
  })
})
