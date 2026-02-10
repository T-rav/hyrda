import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { vi } from 'vitest'
import ToggleSwitch from './ToggleSwitch'

describe('ToggleSwitch', () => {
  it('renders correctly with default props', () => {
    render(<ToggleSwitch id="test-toggle" checked={false} />)

    const toggle = screen.getByRole('checkbox')
    expect(toggle).toBeInTheDocument()
    expect(toggle).not.toBeChecked()
  })

  it('renders in checked state', () => {
    render(<ToggleSwitch id="test-toggle" checked={true} />)

    const toggle = screen.getByRole('checkbox')
    expect(toggle).toBeChecked()
  })

  it('displays custom labels', () => {
    render(
      <ToggleSwitch
        id="test-toggle"
        checked={true}
        labelOn="Enabled"
        labelOff="Disabled"
      />
    )

    expect(screen.getByText('Enabled')).toBeInTheDocument()
  })

  it('displays unchecked label', () => {
    render(
      <ToggleSwitch
        id="test-toggle"
        checked={false}
        labelOn="Enabled"
        labelOff="Disabled"
      />
    )

    expect(screen.getByText('Disabled')).toBeInTheDocument()
  })

  it('displays label when provided', () => {
    render(
      <ToggleSwitch
        id="test-toggle"
        checked={false}
        label="My Toggle Label"
      />
    )

    expect(screen.getByText('My Toggle Label')).toBeInTheDocument()
  })

  it('displays help text when provided', () => {
    render(
      <ToggleSwitch
        id="test-toggle"
        checked={false}
        helpText="This is helpful information"
      />
    )

    expect(screen.getByText('This is helpful information')).toBeInTheDocument()
  })

  it('calls onChange when toggled', () => {
    const handleChange = vi.fn()
    render(
      <ToggleSwitch
        id="test-toggle"
        checked={false}
        onChange={handleChange}
      />
    )

    const toggle = screen.getByRole('checkbox')
    fireEvent.click(toggle)

    expect(handleChange).toHaveBeenCalledWith(true)
  })

  it('does not call onChange when disabled', () => {
    const handleChange = vi.fn()
    render(
      <ToggleSwitch
        id="test-toggle"
        checked={false}
        disabled={true}
        onChange={handleChange}
      />
    )

    const toggle = screen.getByRole('checkbox')
    fireEvent.click(toggle)

    expect(handleChange).not.toHaveBeenCalled()
  })

  it('has disabled attribute when disabled', () => {
    render(
      <ToggleSwitch
        id="test-toggle"
        checked={false}
        disabled={true}
      />
    )

    const toggle = screen.getByRole('checkbox')
    expect(toggle).toBeDisabled()
  })

  it('applies disabled class to container when disabled', () => {
    const { container } = render(
      <ToggleSwitch
        id="test-toggle"
        checked={false}
        disabled={true}
      />
    )

    const toggleLabel = container.querySelector('.toggle-switch')
    expect(toggleLabel).toHaveClass('disabled')
  })
})
