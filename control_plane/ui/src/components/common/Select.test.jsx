import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import Select from './Select'

describe('Select', () => {
  const mockOptions = [
    { value: 'option1', label: 'Option 1' },
    { value: 'option2', label: 'Option 2' },
    { value: 'option3', label: 'Option 3', disabled: true },
  ]

  describe('rendering', () => {
    it('renders select with options', () => {
      render(<Select options={mockOptions} />)
      expect(screen.getByRole('combobox')).toBeInTheDocument()
    })

    it('renders label when provided', () => {
      render(<Select label="Choose option" options={mockOptions} />)
      expect(screen.getByText('Choose option')).toBeInTheDocument()
    })

    it('renders placeholder when provided', () => {
      render(<Select placeholder="Select an option" options={mockOptions} />)
      expect(screen.getByText('Select an option')).toBeInTheDocument()
    })

    it('renders all options', () => {
      render(<Select options={mockOptions} />)
      expect(screen.getByText('Option 1')).toBeInTheDocument()
      expect(screen.getByText('Option 2')).toBeInTheDocument()
      expect(screen.getByText('Option 3')).toBeInTheDocument()
    })

    it('renders disabled option', () => {
      render(<Select options={mockOptions} />)
      const disabledOption = screen.getByText('Option 3')
      expect(disabledOption).toBeDisabled()
    })

    it('renders with correct value', () => {
      render(<Select options={mockOptions} value="option2" />)
      expect(screen.getByRole('combobox')).toHaveValue('option2')
    })
  })

  describe('states', () => {
    it('disables select when disabled is true', () => {
      render(<Select options={mockOptions} disabled />)
      expect(screen.getByRole('combobox')).toBeDisabled()
    })

    it('marks as required when required is true', () => {
      render(<Select label="Choose" options={mockOptions} required />)
      expect(screen.getByRole('combobox')).toBeRequired()
    })

    it('shows required indicator on label', () => {
      render(<Select label="Choose" options={mockOptions} required />)
      expect(screen.getByText('*')).toBeInTheDocument()
    })

    it('applies error class when error is provided', () => {
      render(<Select options={mockOptions} error="Selection required" />)
      expect(screen.getByRole('combobox')).toHaveClass('input-error')
    })

    it('renders error message when error is provided', () => {
      render(<Select options={mockOptions} error="Selection required" />)
      expect(screen.getByText('Selection required')).toBeInTheDocument()
    })

    it('renders hint text when provided', () => {
      render(<Select options={mockOptions} hint="Choose wisely" />)
      expect(screen.getByText('Choose wisely')).toBeInTheDocument()
    })
  })

  describe('interactions', () => {
    it('calls onChange when selection changes', () => {
      const handleChange = jest.fn()
      render(<Select options={mockOptions} onChange={handleChange} />)
      const select = screen.getByRole('combobox')
      fireEvent.change(select, { target: { value: 'option2' } })
      expect(handleChange).toHaveBeenCalled()
    })
  })

  describe('accessibility', () => {
    it('has correct combobox role', () => {
      render(<Select options={mockOptions} />)
      expect(screen.getByRole('combobox')).toBeInTheDocument()
    })

    it('sets aria-invalid when error is provided', () => {
      render(<Select options={mockOptions} error="Invalid" />)
      expect(screen.getByRole('combobox')).toHaveAttribute('aria-invalid', 'true')
    })

    it('associates label with select', () => {
      render(<Select label="Test Label" id="test-select" options={mockOptions} />)
      const label = screen.getByText('Test Label')
      const select = screen.getByRole('combobox')
      expect(label).toHaveAttribute('for', 'test-select')
      expect(select).toHaveAttribute('id', 'test-select')
    })

    it('error message has role="alert"', () => {
      render(<Select options={mockOptions} error="Invalid selection" />)
      expect(screen.getByRole('alert')).toHaveTextContent('Invalid selection')
    })
  })

  describe('structure', () => {
    it('has select-wrapper class', () => {
      render(<Select options={mockOptions} />)
      expect(document.querySelector('.select-wrapper')).toBeInTheDocument()
    })

    it('has select-container for positioning', () => {
      render(<Select options={mockOptions} />)
      expect(document.querySelector('.select-container')).toBeInTheDocument()
    })

    it('has chevron icon', () => {
      render(<Select options={mockOptions} />)
      expect(document.querySelector('.select-icon')).toBeInTheDocument()
    })
  })
})
