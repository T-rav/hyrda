import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import Textarea from './Textarea'

describe('Textarea', () => {
  describe('rendering', () => {
    it('renders textarea correctly', () => {
      render(<Textarea />)
      expect(screen.getByRole('textbox')).toBeInTheDocument()
    })

    it('renders label when provided', () => {
      render(<Textarea label="Description" />)
      expect(screen.getByText('Description')).toBeInTheDocument()
    })

    it('renders placeholder text', () => {
      render(<Textarea placeholder="Enter description" />)
      expect(screen.getByPlaceholderText('Enter description')).toBeInTheDocument()
    })

    it('renders value correctly', () => {
      render(<Textarea value="Test value" onChange={() => {}} />)
      expect(screen.getByDisplayValue('Test value')).toBeInTheDocument()
    })

    it('renders with default rows of 3', () => {
      render(<Textarea />)
      expect(screen.getByRole('textbox')).toHaveAttribute('rows', '3')
    })

    it('renders with custom rows', () => {
      render(<Textarea rows={5} />)
      expect(screen.getByRole('textbox')).toHaveAttribute('rows', '5')
    })

    it('applies custom className', () => {
      render(<Textarea className="custom-textarea" />)
      expect(document.querySelector('.custom-textarea')).toBeInTheDocument()
    })
  })

  describe('states', () => {
    it('shows required indicator when required', () => {
      render(<Textarea label="Description" required />)
      expect(screen.getByText('*')).toHaveClass('text-danger')
    })

    it('disables textarea when disabled is true', () => {
      render(<Textarea disabled />)
      expect(screen.getByRole('textbox')).toBeDisabled()
    })

    it('applies is-invalid class when error is provided', () => {
      render(<Textarea error="Required field" />)
      expect(screen.getByRole('textbox')).toHaveClass('is-invalid')
    })

    it('renders error message when error is provided', () => {
      render(<Textarea error="Required field" />)
      expect(screen.getByText('Required field')).toHaveClass('invalid-feedback')
    })

    it('renders hint text when provided', () => {
      render(<Textarea hint="Maximum 500 characters" />)
      expect(screen.getByText('Maximum 500 characters')).toHaveClass('form-text')
    })

    it('applies no-resize class when resize is false', () => {
      render(<Textarea resize={false} />)
      expect(screen.getByRole('textbox')).toHaveClass('no-resize')
    })

    it('allows resize by default', () => {
      render(<Textarea />)
      expect(screen.getByRole('textbox')).not.toHaveClass('no-resize')
    })
  })

  describe('interactions', () => {
    it('calls onChange when textarea value changes', () => {
      const handleChange = jest.fn()
      render(<Textarea onChange={handleChange} />)
      const textarea = screen.getByRole('textbox')
      fireEvent.change(textarea, { target: { value: 'New value' } })
      expect(handleChange).toHaveBeenCalled()
    })
  })

  describe('accessibility', () => {
    it('has correct textbox role', () => {
      render(<Textarea />)
      expect(screen.getByRole('textbox')).toBeInTheDocument()
    })

    it('sets aria-invalid when error is provided', () => {
      render(<Textarea error="Invalid" />)
      expect(screen.getByRole('textbox')).toHaveAttribute('aria-invalid', 'true')
    })

    it('sets aria-invalid to false when no error', () => {
      render(<Textarea />)
      expect(screen.getByRole('textbox')).toHaveAttribute('aria-invalid', 'false')
    })

    it('associates error message with aria-describedby', () => {
      render(<Textarea id="test-textarea" error="Invalid input" />)
      const textarea = screen.getByRole('textbox')
      const errorMessage = screen.getByText('Invalid input')
      expect(textarea).toHaveAttribute('aria-describedby', errorMessage.id)
    })

    it('error message has role="alert"', () => {
      render(<Textarea error="Invalid input" />)
      expect(screen.getByRole('alert')).toHaveTextContent('Invalid input')
    })

    it('associates hint with aria-describedby', () => {
      render(<Textarea id="test-textarea" hint="Helpful hint" />)
      const textarea = screen.getByRole('textbox')
      const hint = screen.getByText('Helpful hint')
      expect(textarea).toHaveAttribute('aria-describedby', hint.id)
    })

    it('supports autoFocus', () => {
      render(<Textarea autoFocus />)
      expect(screen.getByRole('textbox')).toHaveFocus()
    })
  })

  describe('structure', () => {
    it('has mb-4 class on wrapper', () => {
      render(<Textarea />)
      expect(document.querySelector('.mb-4')).toBeInTheDocument()
    })

    it('has form-control class', () => {
      render(<Textarea />)
      expect(screen.getByRole('textbox')).toHaveClass('form-control')
    })

    it('has textarea element', () => {
      render(<Textarea />)
      expect(screen.getByRole('textbox').tagName).toBe('TEXTAREA')
    })
  })
})
