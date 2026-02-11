import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { Search, Eye } from 'lucide-react'
import Input from './Input'

describe('Input', () => {
  describe('rendering', () => {
    it('renders input correctly', () => {
      render(<Input />)
      expect(screen.getByRole('textbox')).toBeInTheDocument()
    })

    it('renders with default type="text"', () => {
      render(<Input />)
      expect(screen.getByRole('textbox')).toHaveAttribute('type', 'text')
    })

    it('renders with custom type', () => {
      render(<Input type="email" />)
      expect(screen.getByRole('textbox')).toHaveAttribute('type', 'email')
    })

    it('renders label when provided', () => {
      render(<Input label="Email Address" />)
      expect(screen.getByText('Email Address')).toBeInTheDocument()
    })

    it('associates label with input', () => {
      render(<Input label="Email" id="email-input" />)
      const label = screen.getByText('Email')
      const input = screen.getByRole('textbox')
      expect(label).toHaveAttribute('for', 'email-input')
      expect(input).toHaveAttribute('id', 'email-input')
    })

    it('renders placeholder text', () => {
      render(<Input placeholder="Enter your email" />)
      expect(screen.getByPlaceholderText('Enter your email')).toBeInTheDocument()
    })

    it('renders value correctly', () => {
      render(<Input value="test@example.com" onChange={() => {}} />)
      expect(screen.getByDisplayValue('test@example.com')).toBeInTheDocument()
    })

    it('renders left icon', () => {
      render(<Input leftIcon={<Search data-testid="search-icon" />} />)
      expect(screen.getByTestId('search-icon')).toBeInTheDocument()
    })

    it('renders right icon', () => {
      render(<Input rightIcon={<Eye data-testid="eye-icon" />} />)
      expect(screen.getByTestId('eye-icon')).toBeInTheDocument()
    })

    it('applies custom className', () => {
      render(<Input className="custom-input" />)
      expect(document.querySelector('.input-wrapper')).toHaveClass('custom-input')
    })

    it('renders with name attribute', () => {
      render(<Input name="email" />)
      expect(screen.getByRole('textbox')).toHaveAttribute('name', 'email')
    })
  })

  describe('sizes', () => {
    it('does not apply size class for md by default', () => {
      render(<Input />)
      const input = screen.getByRole('textbox')
      expect(input).not.toHaveClass('input-sm')
      expect(input).not.toHaveClass('input-lg')
    })

    it('applies sm size class', () => {
      render(<Input size="sm" />)
      expect(screen.getByRole('textbox')).toHaveClass('input-sm')
    })

    it('applies lg size class', () => {
      render(<Input size="lg" />)
      expect(screen.getByRole('textbox')).toHaveClass('input-lg')
    })
  })

  describe('states', () => {
    it('shows required indicator when required', () => {
      render(<Input label="Email" required />)
      expect(screen.getByText('*')).toBeInTheDocument()
    })

    it('disables input when disabled is true', () => {
      render(<Input disabled />)
      expect(screen.getByRole('textbox')).toBeDisabled()
    })

    it('applies error class when error is provided', () => {
      render(<Input error="Invalid email" />)
      expect(screen.getByRole('textbox')).toHaveClass('input-error')
    })

    it('renders error message when error is provided', () => {
      render(<Input error="Invalid email" />)
      expect(screen.getByText('Invalid email')).toBeInTheDocument()
    })

    it('renders hint text when provided', () => {
      render(<Input hint="We will never share your email" />)
      expect(screen.getByText('We will never share your email')).toBeInTheDocument()
    })
  })

  describe('interactions', () => {
    it('calls onChange when input value changes', () => {
      const handleChange = jest.fn()
      render(<Input onChange={handleChange} />)
      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: 'test' } })
      expect(handleChange).toHaveBeenCalled()
    })
  })

  describe('accessibility', () => {
    it('has correct textbox role', () => {
      render(<Input />)
      expect(screen.getByRole('textbox')).toBeInTheDocument()
    })

    it('sets aria-invalid when error is provided', () => {
      render(<Input error="Invalid" />)
      expect(screen.getByRole('textbox')).toHaveAttribute('aria-invalid', 'true')
    })

    it('sets aria-invalid to false when no error', () => {
      render(<Input />)
      expect(screen.getByRole('textbox')).toHaveAttribute('aria-invalid', 'false')
    })

    it('sets aria-required when required', () => {
      render(<Input required />)
      expect(screen.getByRole('textbox')).toHaveAttribute('aria-required', 'true')
    })

    it('associates error message with aria-describedby', () => {
      render(<Input id="test-input" error="Invalid email" />)
      const input = screen.getByRole('textbox')
      const errorMessage = screen.getByText('Invalid email')
      expect(input).toHaveAttribute('aria-describedby', errorMessage.id)
    })

    it('error message has role="alert"', () => {
      render(<Input error="Invalid email" />)
      expect(screen.getByRole('alert')).toHaveTextContent('Invalid email')
    })

    it('hides icons from screen readers', () => {
      render(<Input leftIcon={<Search data-testid="icon" />} />)
      const icon = screen.getByTestId('icon').parentElement
      expect(icon).toHaveAttribute('aria-hidden', 'true')
    })

    it('supports autoFocus', () => {
      render(<Input autoFocus />)
      expect(screen.getByRole('textbox')).toHaveFocus()
    })
  })
})
