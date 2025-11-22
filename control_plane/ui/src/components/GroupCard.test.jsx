/**
 * Tests for GroupCard component
 */

import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import GroupCard from './GroupCard'

describe('GroupCard', () => {
  const mockGroup = {
    group_name: 'test_group',
    display_name: 'Test Group',
    description: 'A test group',
    user_count: 5,
    users: []
  }

  const mockCallbacks = {
    onEdit: jest.fn(),
    onManageUsers: jest.fn(),
    onManageAgents: jest.fn(),
    onDelete: jest.fn(),
  }

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('should render group name and description', () => {
    render(<GroupCard group={mockGroup} {...mockCallbacks} />)

    expect(screen.getByText('Test Group')).toBeInTheDocument()
    expect(screen.getByText('A test group')).toBeInTheDocument()
  })

  it('should display user count', () => {
    render(<GroupCard group={mockGroup} {...mockCallbacks} />)

    expect(screen.getByText('5 users')).toBeInTheDocument()
  })

  it('should render system badge for system groups', () => {
    const systemGroup = {
      ...mockGroup,
      group_name: 'all_users',
      display_name: 'All Users'
    }

    render(<GroupCard group={systemGroup} {...mockCallbacks} />)

    expect(screen.getByText('System Group')).toBeInTheDocument()
  })

  it('should call onEdit when Edit button clicked', () => {
    render(<GroupCard group={mockGroup} {...mockCallbacks} />)

    const editButton = screen.getByText('Edit').closest('button')
    fireEvent.click(editButton)

    expect(mockCallbacks.onEdit).toHaveBeenCalledWith(mockGroup)
  })

  it('should call onManageUsers when Manage Users button clicked', () => {
    render(<GroupCard group={mockGroup} {...mockCallbacks} />)

    const manageUsersButton = screen.getByText('Manage Users').closest('button')
    fireEvent.click(manageUsersButton)

    expect(mockCallbacks.onManageUsers).toHaveBeenCalledWith(mockGroup)
  })

  it('should call onManageAgents when Manage Agents button clicked', () => {
    render(<GroupCard group={mockGroup} {...mockCallbacks} />)

    const manageAgentsButton = screen.getByText('Manage Agents').closest('button')
    fireEvent.click(manageAgentsButton)

    expect(mockCallbacks.onManageAgents).toHaveBeenCalledWith(mockGroup)
  })

  it('should show delete button for non-system groups', () => {
    render(<GroupCard group={mockGroup} {...mockCallbacks} />)

    expect(screen.getByText('Delete')).toBeInTheDocument()
  })

  it('should not show delete button for system groups', () => {
    const systemGroup = {
      ...mockGroup,
      group_name: 'all_users'
    }

    render(<GroupCard group={systemGroup} {...mockCallbacks} />)

    expect(screen.queryByText('Delete')).not.toBeInTheDocument()
  })

  it('should show confirmation dialog when delete button clicked', () => {
    global.confirm = jest.fn(() => false)

    render(<GroupCard group={mockGroup} {...mockCallbacks} />)

    const deleteButton = screen.getByText('Delete').closest('button')
    fireEvent.click(deleteButton)

    expect(global.confirm).toHaveBeenCalledWith(
      expect.stringContaining('Test Group')
    )
  })

  it('should call onDelete when deletion confirmed', () => {
    global.confirm = jest.fn(() => true)

    render(<GroupCard group={mockGroup} {...mockCallbacks} />)

    const deleteButton = screen.getByText('Delete').closest('button')
    fireEvent.click(deleteButton)

    expect(mockCallbacks.onDelete).toHaveBeenCalledWith('test_group')
  })

  it('should not call onDelete when deletion cancelled', () => {
    global.confirm = jest.fn(() => false)

    render(<GroupCard group={mockGroup} {...mockCallbacks} />)

    const deleteButton = screen.getByText('Delete').closest('button')
    fireEvent.click(deleteButton)

    expect(mockCallbacks.onDelete).not.toHaveBeenCalled()
  })

  it('should pluralize user count correctly', () => {
    const singleUserGroup = { ...mockGroup, user_count: 1 }
    const { rerender } = render(<GroupCard group={singleUserGroup} {...mockCallbacks} />)

    expect(screen.getByText('1 user')).toBeInTheDocument()

    const multipleUsersGroup = { ...mockGroup, user_count: 3 }
    rerender(<GroupCard group={multipleUsersGroup} {...mockCallbacks} />)

    expect(screen.getByText('3 users')).toBeInTheDocument()
  })
})
