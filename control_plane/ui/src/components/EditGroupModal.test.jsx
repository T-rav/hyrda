/**
 * Tests for EditGroupModal component
 */

import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import EditGroupModal from './EditGroupModal'

describe('EditGroupModal', () => {
  const mockGroup = {
    group_name: 'test_group',
    display_name: 'Test Group',
    description: 'A test group'
  }

  const mockCallbacks = {
    onClose: jest.fn(),
    onUpdate: jest.fn(),
  }

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('should render modal with group data', () => {
    render(<EditGroupModal group={mockGroup} {...mockCallbacks} />)

    expect(screen.getByText('Edit Group')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Test Group')).toBeInTheDocument()
    expect(screen.getByDisplayValue('A test group')).toBeInTheDocument()
  })

  it('should call onClose when close button clicked', () => {
    render(<EditGroupModal group={mockGroup} {...mockCallbacks} />)

    const closeButton = document.querySelector('.modal-close')
    fireEvent.click(closeButton)

    expect(mockCallbacks.onClose).toHaveBeenCalled()
  })

  it('should call onClose when Cancel button clicked', () => {
    render(<EditGroupModal group={mockGroup} {...mockCallbacks} />)

    const cancelButton = screen.getByText('Cancel')
    fireEvent.click(cancelButton)

    expect(mockCallbacks.onClose).toHaveBeenCalled()
  })

  it('should update display name input', () => {
    render(<EditGroupModal group={mockGroup} {...mockCallbacks} />)

    const displayNameInput = screen.getByDisplayValue('Test Group')
    fireEvent.change(displayNameInput, { target: { value: 'Updated Group' } })

    expect(displayNameInput.value).toBe('Updated Group')
  })

  it('should update description textarea', () => {
    render(<EditGroupModal group={mockGroup} {...mockCallbacks} />)

    const descriptionTextarea = screen.getByDisplayValue('A test group')
    fireEvent.change(descriptionTextarea, { target: { value: 'Updated description' } })

    expect(descriptionTextarea.value).toBe('Updated description')
  })

  it('should call onUpdate with updated data on form submit', () => {
    render(<EditGroupModal group={mockGroup} {...mockCallbacks} />)

    const displayNameInput = screen.getByDisplayValue('Test Group')
    const descriptionTextarea = screen.getByDisplayValue('A test group')

    fireEvent.change(displayNameInput, { target: { value: 'Updated Group' } })
    fireEvent.change(descriptionTextarea, { target: { value: 'Updated description' } })

    const form = screen.getByRole('button', { name: /save changes/i }).closest('form')
    fireEvent.submit(form)

    expect(mockCallbacks.onUpdate).toHaveBeenCalledWith('test_group', {
      display_name: 'Updated Group',
      description: 'Updated description'
    })
  })

  it('should require display name input', () => {
    render(<EditGroupModal group={mockGroup} {...mockCallbacks} />)

    const displayNameInput = screen.getByDisplayValue('Test Group')

    // Verify the input has the required attribute
    expect(displayNameInput).toHaveAttribute('required')
  })

  it('should allow empty description', () => {
    render(<EditGroupModal group={mockGroup} {...mockCallbacks} />)

    const descriptionTextarea = screen.getByDisplayValue('A test group')
    fireEvent.change(descriptionTextarea, { target: { value: '' } })

    const form = screen.getByRole('button', { name: /save changes/i }).closest('form')
    fireEvent.submit(form)

    expect(mockCallbacks.onUpdate).toHaveBeenCalledWith('test_group', {
      display_name: 'Test Group',
      description: ''
    })
  })

  it('should handle group with no description', () => {
    const groupWithoutDesc = {
      group_name: 'test_group',
      display_name: 'Test Group',
      description: null
    }

    render(<EditGroupModal group={groupWithoutDesc} {...mockCallbacks} />)

    const descriptionTextarea = screen.getByPlaceholderText('Team members who analyze data')
    expect(descriptionTextarea.value).toBe('')
  })

  it('should close modal on overlay click', () => {
    render(<EditGroupModal group={mockGroup} {...mockCallbacks} />)

    const overlay = screen.getByText('Edit Group').closest('.modal-overlay')
    fireEvent.click(overlay)

    expect(mockCallbacks.onClose).toHaveBeenCalled()
  })

  it('should not close modal when clicking inside modal content', () => {
    render(<EditGroupModal group={mockGroup} {...mockCallbacks} />)

    const modalContent = screen.getByText('Edit Group').closest('.modal-content')
    fireEvent.click(modalContent)

    expect(mockCallbacks.onClose).not.toHaveBeenCalled()
  })
})
