import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ManageGroupUsersModal from './ManageGroupUsersModal'

describe('ManageGroupUsersModal', () => {
  const mockGroup = {
    group_name: 'test-group',
    display_name: 'Test Group',
    users: [{ slack_user_id: 'U123', full_name: 'User One' }]
  }

  const mockUsers = [
    { id: '1', slack_user_id: 'U123', full_name: 'User One', email: 'user1@test.com' },
    { id: '2', slack_user_id: 'U456', full_name: 'User Two', email: 'user2@test.com' },
    { id: '3', slack_user_id: 'U789', full_name: 'User Three', email: 'user3@test.com' }
  ]

  const mockOnClose = jest.fn()
  const mockOnAddUser = jest.fn()
  const mockOnRemoveUser = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders correctly with group and users', () => {
    render(
      <ManageGroupUsersModal
        group={mockGroup}
        users={mockUsers}
        onClose={mockOnClose}
        onAddUser={mockOnAddUser}
        onRemoveUser={mockOnRemoveUser}
      />
    )

    expect(screen.getByText('Manage Users: Test Group')).toBeInTheDocument()
    expect(screen.getByText('User One')).toBeInTheDocument()
    expect(screen.getByText('User Two')).toBeInTheDocument()
  })

  it('shows In Group badge for users already in group', () => {
    render(
      <ManageGroupUsersModal
        group={mockGroup}
        users={mockUsers}
        onClose={mockOnClose}
        onAddUser={mockOnAddUser}
        onRemoveUser={mockOnRemoveUser}
      />
    )

    expect(screen.getByText('In Group')).toBeInTheDocument()
  })

  it('shows Add button for users not in group', () => {
    render(
      <ManageGroupUsersModal
        group={mockGroup}
        users={mockUsers}
        onClose={mockOnClose}
        onAddUser={mockOnAddUser}
        onRemoveUser={mockOnRemoveUser}
      />
    )

    const addButtons = screen.getAllByText('Add')
    expect(addButtons.length).toBeGreaterThan(0)
  })

  it('shows Remove button for users in group', () => {
    render(
      <ManageGroupUsersModal
        group={mockGroup}
        users={mockUsers}
        onClose={mockOnClose}
        onAddUser={mockOnAddUser}
        onRemoveUser={mockOnRemoveUser}
      />
    )

    expect(screen.getByText('Remove')).toBeInTheDocument()
  })

  it('calls onAddUser when Add button is clicked', async () => {
    mockOnAddUser.mockResolvedValueOnce()

    render(
      <ManageGroupUsersModal
        group={mockGroup}
        users={mockUsers}
        onClose={mockOnClose}
        onAddUser={mockOnAddUser}
        onRemoveUser={mockOnRemoveUser}
      />
    )

    const addButton = screen.getAllByText('Add')[0]
    fireEvent.click(addButton)

    await waitFor(() => {
      expect(mockOnAddUser).toHaveBeenCalledWith('U456')
    })
  })

  it('calls onRemoveUser when Remove button is clicked', async () => {
    mockOnRemoveUser.mockResolvedValueOnce()

    render(
      <ManageGroupUsersModal
        group={mockGroup}
        users={mockUsers}
        onClose={mockOnClose}
        onAddUser={mockOnAddUser}
        onRemoveUser={mockOnRemoveUser}
      />
    )

    const removeButton = screen.getByText('Remove')
    fireEvent.click(removeButton)

    await waitFor(() => {
      expect(mockOnRemoveUser).toHaveBeenCalledWith('U123')
    })
  })

  it('optimistically updates UI when Add is clicked', async () => {
    mockOnAddUser.mockResolvedValueOnce()

    render(
      <ManageGroupUsersModal
        group={mockGroup}
        users={mockUsers}
        onClose={mockOnClose}
        onAddUser={mockOnAddUser}
        onRemoveUser={mockOnRemoveUser}
      />
    )

    // Initially User Two shows Add button
    const userTwoSection = screen.getByText('User Two').closest('.user-selection-item')
    expect(userTwoSection).toHaveTextContent('Add')

    // Click Add
    const addButton = screen.getAllByText('Add')[0]
    fireEvent.click(addButton)

    // UI should immediately show Remove (optimistic update)
    await waitFor(() => {
      expect(userTwoSection).toHaveTextContent('Remove')
    })
  })

  it('optimistically updates UI when Remove is clicked', async () => {
    mockOnRemoveUser.mockResolvedValueOnce()

    render(
      <ManageGroupUsersModal
        group={mockGroup}
        users={mockUsers}
        onClose={mockOnClose}
        onAddUser={mockOnAddUser}
        onRemoveUser={mockOnRemoveUser}
      />
    )

    // Initially User One shows Remove button
    const userOneSection = screen.getByText('User One').closest('.user-selection-item')
    expect(userOneSection).toHaveTextContent('Remove')

    // Click Remove
    const removeButton = screen.getByText('Remove')
    fireEvent.click(removeButton)

    // UI should immediately show Add (optimistic update)
    await waitFor(() => {
      expect(userOneSection).toHaveTextContent('Add')
    })
  })

  it('reverts UI on add error', async () => {
    mockOnAddUser.mockRejectedValueOnce(new Error('Failed to add'))

    render(
      <ManageGroupUsersModal
        group={mockGroup}
        users={mockUsers}
        onClose={mockOnClose}
        onAddUser={mockOnAddUser}
        onRemoveUser={mockOnRemoveUser}
      />
    )

    // Click Add
    const addButton = screen.getAllByText('Add')[0]
    fireEvent.click(addButton)

    // Wait for error handling
    await waitFor(() => {
      expect(mockOnAddUser).toHaveBeenCalled()
    })

    // UI should revert to Add button
    await waitFor(() => {
      const userTwoSection = screen.getByText('User Two').closest('.user-selection-item')
      expect(userTwoSection).toHaveTextContent('Add')
    })
  })

  it('filters users based on search term', () => {
    render(
      <ManageGroupUsersModal
        group={mockGroup}
        users={mockUsers}
        onClose={mockOnClose}
        onAddUser={mockOnAddUser}
        onRemoveUser={mockOnRemoveUser}
      />
    )

    const searchInput = screen.getByPlaceholderText('Search users...')
    fireEvent.change(searchInput, { target: { value: 'User Two' } })

    expect(screen.getByText('User Two')).toBeInTheDocument()
    expect(screen.queryByText('User Three')).not.toBeInTheDocument()
  })

  it('calls onClose when close button is clicked', () => {
    render(
      <ManageGroupUsersModal
        group={mockGroup}
        users={mockUsers}
        onClose={mockOnClose}
        onAddUser={mockOnAddUser}
        onRemoveUser={mockOnRemoveUser}
      />
    )

    const closeButton = document.querySelector('.modal-close')
    fireEvent.click(closeButton)

    expect(mockOnClose).toHaveBeenCalled()
  })

  it('shows warning for system group', () => {
    const systemGroup = {
      ...mockGroup,
      group_name: 'all_users',
      display_name: 'All Users'
    }

    render(
      <ManageGroupUsersModal
        group={systemGroup}
        users={mockUsers}
        onClose={mockOnClose}
        onAddUser={mockOnAddUser}
        onRemoveUser={mockOnRemoveUser}
      />
    )

    expect(screen.getByText(/System group/)).toBeInTheDocument()
    expect(screen.getByText('Auto-added')).toBeInTheDocument()
  })
})
