import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react'
import { IntentInput, inputContainerStyle, inputButtonStyle, inputButtonDisabledStyle } from '../IntentInput'

beforeEach(() => cleanup())

describe('IntentInput', () => {
  it('renders input and send button', () => {
    render(<IntentInput onSubmit={() => {}} />)
    expect(screen.getByPlaceholderText('What do you want to build?')).toBeInTheDocument()
    expect(screen.getByText('Send')).toBeInTheDocument()
  })

  it('calls onSubmit with trimmed text', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<IntentInput onSubmit={onSubmit} />)

    const input = screen.getByPlaceholderText('What do you want to build?')
    fireEvent.change(input, { target: { value: '  add rate limiting  ' } })
    fireEvent.click(screen.getByText('Send'))

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith('add rate limiting')
    })
  })

  it('clears input after successful submission', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<IntentInput onSubmit={onSubmit} />)

    const input = screen.getByPlaceholderText('What do you want to build?')
    fireEvent.change(input, { target: { value: 'test intent' } })
    fireEvent.click(screen.getByText('Send'))

    await waitFor(() => {
      expect(input.value).toBe('')
    })
  })

  it('disables button when input is empty', () => {
    render(<IntentInput onSubmit={() => {}} />)
    const button = screen.getByText('Send')
    expect(button.disabled).toBe(true)
  })

  it('enables button when input has text', () => {
    render(<IntentInput onSubmit={() => {}} />)
    const input = screen.getByPlaceholderText('What do you want to build?')
    fireEvent.change(input, { target: { value: 'something' } })
    const button = screen.getByText('Send')
    expect(button.disabled).toBe(false)
  })

  it('does not submit on whitespace-only input', () => {
    const onSubmit = vi.fn()
    render(<IntentInput onSubmit={onSubmit} />)

    const input = screen.getByPlaceholderText('What do you want to build?')
    fireEvent.change(input, { target: { value: '   ' } })
    fireEvent.click(screen.getByText('Send'))

    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits on Enter key press', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<IntentInput onSubmit={onSubmit} />)

    const input = screen.getByPlaceholderText('What do you want to build?')
    fireEvent.change(input, { target: { value: 'test' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith('test')
    })
  })
})

describe('IntentInput pre-computed styles', () => {
  it('container has flex layout', () => {
    expect(inputContainerStyle).toMatchObject({
      display: 'flex',
      gap: 10,
    })
  })

  it('button styles differ from disabled styles', () => {
    expect(inputButtonStyle.background).not.toBe(inputButtonDisabledStyle.background)
  })

  it('style objects are referentially stable', () => {
    expect(inputContainerStyle).toBe(inputContainerStyle)
    expect(inputButtonStyle).toBe(inputButtonStyle)
    expect(inputButtonDisabledStyle).toBe(inputButtonDisabledStyle)
  })
})
