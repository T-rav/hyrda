import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ManageUserGroupsModal from './ManageUserGroupsModal'

describe('ManageUserGroupsModal', () => {
  const mockUser = {
    slack_user_id: 'U123',
    full_name: 'Test User',
    groups: [{ group_name: 'group1', display_name: 'Group 1' }]
  }

  const mockGroups = [
    { group_name: 'group1', display_name: 'Group 1', description: 'First group', user_count: 5 },
    { group_name: 'group2', display_name: 'Group 2', description: 'Second group', user_count: 3 },
    { group_name: 'all_users', display_name: 'All Users', description: 'Everyone', user_count: 10 }
  ]

  const mockOnClose = jest.fn()
  const mockOnAddToGroup = jest.fn()
  const mockOnRemoveFromGroup = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders correctly with user and groups', () => {
    render(
      <ManageUserGroupsModal
        user={mockUser}
        groups={mockGroups}
        onClose={mockOnClose}
        onAddToGroup={mockOnAddToGroup}
        onRemoveFromGroup={mockOnRemoveFromGroup}
      />
    )

    expect(screen.getByText('Manage Groups: Test User')).toBeInTheDocument()
    expect(screen.getByText('Group 1')).toBeInTheDocument()
    expect(screen.getByText('Group 2')).toBeInTheDocument()
  })

  it('shows Member badge for groups user is already in', () => {
    render(
      <ManageUserGroupsModal
        user={mockUser}
        groups={mockGroups}
        onClose={mockOnClose}
        onAddToGroup={mockOnAddToGroup}
        onRemoveFromGroup={mockOnRemoveFromGroup}
      />
    )

    expect(screen.getByText('Member')).toBeInTheDocument()
  })

  it('shows Add button for groups user is not in', () => {
    render(
      <ManageUserGroupsModal
        user={mockUser}
        groups={mockGroups}
        onClose={mockOnClose}
        onAddToGroup={mockOnAddToGroup}
        onRemoveFromGroup={mockOnRemoveFromGroup}
      />
    )

    const addButtons = screen.getAllByText('Add')
    expect(addButtons.length).toBeGreaterThan(0)
  })

  it('shows Remove button for groups user is in', () => {
    render(
      <ManageUserGroupsModal
        user={mockUser}
        groups={mockGroups}
        onClose={mockOnClose}
        onAddToGroup={mockOnAddToGroup}
        onRemoveFromGroup={mockOnRemoveFromGroup}
      />
    )

    expect(screen.getByText('Remove')).toBeInTheDocument()
  })

  it('calls onAddToGroup when Add button is clicked', async () => {
    mockOnAddToGroup.mockResolvedValueOnce()

    render(
      <ManageUserGroupsModal
        user={mockUser}
        groups={mockGroups}
        onClose={mockOnClose}
        onAddToGroup={mockOnAddToGroup}
        onRemoveFromGroup={mockOnRemoveFromGroup}
      />
    )

    const addButton = screen.getAllByText('Add')[0]
    fireEvent.click(addButton)

    await waitFor(() => {
      expect(mockOnAddToGroup).toHaveBeenCalledWith('group2', 'U123')
    })
  })

  it('calls onRemoveFromGroup when Remove button is clicked', async () => {
    mockOnRemoveFromGroup.mockResolvedValueOnce()

    render(
      <ManageUserGroupsModal
        user={mockUser}
        groups={mockGroups}
        onClose={mockOnClose}
        onAddToGroup={mockOnAddToGroup}
        onRemoveFromGroup={mockOnRemoveFromGroup}
      />
    )

    const removeButton = screen.getByText('Remove')
    fireEvent.click(removeButton)

    await waitFor(() => {
      expect(mockOnRemoveFromGroup).toHaveBeenCalledWith('group1', 'U123')
    })
  })

  it('optimistically updates UI when Add is clicked', async () => {
    mockOnAddToGroup.mockResolvedValueOnce()

    render(
      <ManageUserGroupsModal
        user={mockUser}
        groups={mockGroups}
        onClose={mockOnClose}
        onAddToGroup={mockOnAddToGroup}
        onRemoveFromGroup={mockOnRemoveFromGroup}
      />
    )

    // Initially Group 2 shows Add button
    const group2Section = screen.getByText('Group 2').closest('.user-selection-item')
    expect(group2Section).toHaveTextContent('Add')

    // Click Add
    const addButton = screen.getAllByText('Add')[0]
    fireEvent.click(addButton)

    // UI should immediately show Remove (optimistic update)
    await waitFor(() => {
      expect(group2Section).toHaveTextContent('Remove')
    })
  })

  it('optimistically updates UI when Remove is clicked', async () => {
    mockOnRemoveFromGroup.mockResolvedValueOnce()

    render(
      <ManageUserGroupsModal
        user={mockUser}
        groups={mockGroups}
        onClose={mockOnClose}
        onAddToGroup={mockOnAddToGroup}
        onRemoveFromGroup={mockOnRemoveFromGroup}
      />
    )

    // Initially Group 1 shows Remove button
    const group1Section = screen.getByText('Group 1').closest('.user-selection-item')
    expect(group1Section).toHaveTextContent('Remove')

    // Click Remove
    const removeButton = screen.getByText('Remove')
    fireEvent.click(removeButton)

    // UI should immediately show Add (optimistic update)
    await waitFor(() => {
      expect(group1Section).toHaveTextContent('Add')
    })
  })

  it('reverts UI on add error', async () => {
    mockOnAddToGroup.mockRejectedValueOnce(new Error('Failed to add'))

    render(
      <ManageUserGroupsModal
        user={mockUser}
        groups={mockGroups}
        onClose={mockOnClose}
        onAddToGroup={mockOnAddToGroup}
        onRemoveFromGroup={mockOnRemoveFromGroup}
      />
    )

    // Click Add
    const addButton = screen.getAllByText('Add')[0]
    fireEvent.click(addButton)

    // Wait for error handling
    await waitFor(() => {
      expect(mockOnAddToGroup).toHaveBeenCalled()
    })

    // UI should revert to Add button
    await waitFor(() => {
      const group2Section = screen.getByText('Group 2').closest('.user-selection-item')
      expect(group2Section).toHaveTextContent('Add')
    })
  })

  it('filters groups based on search term', () => {
    render(
      <ManageUserGroupsModal
        user={mockUser}
        groups={mockGroups}
        onClose={mockOnClose}
        onAddToGroup={mockOnAddToGroup}
        onRemoveFromGroup={mockOnRemoveFromGroup}
      />
    )

    const searchInput = screen.getByPlaceholderText('Search groups...')
    fireEvent.change(searchInput, { target: { value: 'Group 2' } })

    expect(screen.getByText('Group 2')).toBeInTheDocument()
    expect(screen.queryByText('Group 1')).not.toBeInTheDocument()
  })

  it('calls onClose when close button is clicked', () => {
    render(
      <ManageUserGroupsModal
        user={mockUser}
        groups={mockGroups}
        onClose={mockOnClose}
        onAddToGroup={mockOnAddToGroup}
        onRemoveFromGroup={mockOnRemoveFromGroup}
      />
    )

    const closeButton = document.querySelector('.modal-close')
    fireEvent.click(closeButton)

    expect(mockOnClose).toHaveBeenCalled()
  })

  it('hides Add/Remove buttons for system groups', () => {
    render(
      <ManageUserGroupsModal
        user={mockUser}
        groups={mockGroups}
        onClose={mockOnClose}
        onAddToGroup={mockOnAddToGroup}
        onRemoveFromGroup={mockOnRemoveFromGroup}
      />
    )

    const allUsersSection = screen.getByText('All Users').closest('.user-selection-item')
    expect(allUsersSection).not.toHaveTextContent('Add')
    expect(allUsersSection).not.toHaveTextContent('Remove')
  })
})
