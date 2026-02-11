import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ManageAgentAccessModal from './ManageAgentAccessModal'

describe('ManageAgentAccessModal', () => {
  const mockAgent = {
    name: 'test-agent',
    description: 'A test agent',
    is_enabled: true,
    is_system: false,
    authorized_group_names: ['group1']
  }

  const mockGroups = [
    { group_name: 'group1', display_name: 'Group 1', description: 'First group', user_count: 5 },
    { group_name: 'group2', display_name: 'Group 2', description: 'Second group', user_count: 3 },
    { group_name: 'all_users', display_name: 'All Users', description: 'Everyone', user_count: 10 }
  ]

  const mockOnClose = jest.fn()
  const mockOnGrantToGroup = jest.fn()
  const mockOnRevokeFromGroup = jest.fn()
  const mockOnToggle = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders correctly with agent and groups', () => {
    render(
      <ManageAgentAccessModal
        agent={mockAgent}
        groups={mockGroups}
        onClose={mockOnClose}
        onGrantToGroup={mockOnGrantToGroup}
        onRevokeFromGroup={mockOnRevokeFromGroup}
        onToggle={mockOnToggle}

      />
    )

    expect(screen.getByText('Manage Group Access: /test-agent')).toBeInTheDocument()
    expect(screen.getByText('Group 1')).toBeInTheDocument()
    expect(screen.getByText('Group 2')).toBeInTheDocument()
  })

  it('shows Has Access badge for authorized groups', () => {
    render(
      <ManageAgentAccessModal
        agent={mockAgent}
        groups={mockGroups}
        onClose={mockOnClose}
        onGrantToGroup={mockOnGrantToGroup}
        onRevokeFromGroup={mockOnRevokeFromGroup}
        onToggle={mockOnToggle}

      />
    )

    expect(screen.getByText('Has Access')).toBeInTheDocument()
  })

  it('shows Grant button for unauthorized groups', () => {
    render(
      <ManageAgentAccessModal
        agent={mockAgent}
        groups={mockGroups}
        onClose={mockOnClose}
        onGrantToGroup={mockOnGrantToGroup}
        onRevokeFromGroup={mockOnRevokeFromGroup}
        onToggle={mockOnToggle}

      />
    )

    const grantButtons = screen.getAllByText('Grant')
    expect(grantButtons.length).toBeGreaterThan(0)
  })

  it('shows Revoke button for authorized groups', () => {
    render(
      <ManageAgentAccessModal
        agent={mockAgent}
        groups={mockGroups}
        onClose={mockOnClose}
        onGrantToGroup={mockOnGrantToGroup}
        onRevokeFromGroup={mockOnRevokeFromGroup}
        onToggle={mockOnToggle}

      />
    )

    expect(screen.getByText('Revoke')).toBeInTheDocument()
  })

  it('calls onGrantToGroup when Grant button is clicked', async () => {
    mockOnGrantToGroup.mockResolvedValueOnce()

    render(
      <ManageAgentAccessModal
        agent={mockAgent}
        groups={mockGroups}
        onClose={mockOnClose}
        onGrantToGroup={mockOnGrantToGroup}
        onRevokeFromGroup={mockOnRevokeFromGroup}
        onToggle={mockOnToggle}

      />
    )

    const grantButton = screen.getAllByText('Grant')[0]
    fireEvent.click(grantButton)

    await waitFor(() => {
      expect(mockOnGrantToGroup).toHaveBeenCalledWith('group2', 'test-agent')
    })
  })

  it('calls onRevokeFromGroup when Revoke button is clicked', async () => {
    mockOnRevokeFromGroup.mockResolvedValueOnce()

    render(
      <ManageAgentAccessModal
        agent={mockAgent}
        groups={mockGroups}
        onClose={mockOnClose}
        onGrantToGroup={mockOnGrantToGroup}
        onRevokeFromGroup={mockOnRevokeFromGroup}
        onToggle={mockOnToggle}

      />
    )

    const revokeButton = screen.getByText('Revoke')
    fireEvent.click(revokeButton)

    await waitFor(() => {
      expect(mockOnRevokeFromGroup).toHaveBeenCalledWith('group1', 'test-agent')
    })
  })

  it('optimistically updates UI when Grant is clicked', async () => {
    mockOnGrantToGroup.mockResolvedValueOnce()

    render(
      <ManageAgentAccessModal
        agent={mockAgent}
        groups={mockGroups}
        onClose={mockOnClose}
        onGrantToGroup={mockOnGrantToGroup}
        onRevokeFromGroup={mockOnRevokeFromGroup}
        onToggle={mockOnToggle}

      />
    )

    // Initially Group 2 shows Grant button
    const group2Section = screen.getByText('Group 2').closest('.user-selection-item')
    expect(group2Section).toHaveTextContent('Grant')

    // Click Grant
    const grantButton = screen.getAllByText('Grant')[0]
    fireEvent.click(grantButton)

    // UI should immediately show Revoke (optimistic update)
    await waitFor(() => {
      expect(group2Section).toHaveTextContent('Revoke')
    })
  })

  it('optimistically updates UI when Revoke is clicked', async () => {
    mockOnRevokeFromGroup.mockResolvedValueOnce()

    render(
      <ManageAgentAccessModal
        agent={mockAgent}
        groups={mockGroups}
        onClose={mockOnClose}
        onGrantToGroup={mockOnGrantToGroup}
        onRevokeFromGroup={mockOnRevokeFromGroup}
        onToggle={mockOnToggle}

      />
    )

    // Initially Group 1 shows Revoke button
    const group1Section = screen.getByText('Group 1').closest('.user-selection-item')
    expect(group1Section).toHaveTextContent('Revoke')

    // Click Revoke
    const revokeButton = screen.getByText('Revoke')
    fireEvent.click(revokeButton)

    // UI should immediately show Grant (optimistic update)
    await waitFor(() => {
      expect(group1Section).toHaveTextContent('Grant')
    })
  })

  it('reverts UI on grant error', async () => {
    mockOnGrantToGroup.mockRejectedValueOnce(new Error('Failed to grant'))

    render(
      <ManageAgentAccessModal
        agent={mockAgent}
        groups={mockGroups}
        onClose={mockOnClose}
        onGrantToGroup={mockOnGrantToGroup}
        onRevokeFromGroup={mockOnRevokeFromGroup}
        onToggle={mockOnToggle}

      />
    )

    // Click Grant
    const grantButton = screen.getAllByText('Grant')[0]
    fireEvent.click(grantButton)

    // Wait for error handling
    await waitFor(() => {
      expect(mockOnGrantToGroup).toHaveBeenCalled()
    })

    // UI should revert to Grant button
    await waitFor(() => {
      const group2Section = screen.getByText('Group 2').closest('.user-selection-item')
      expect(group2Section).toHaveTextContent('Grant')
    })
  })

  it('shows system agent banner for system agents', () => {
    const systemAgent = {
      ...mockAgent,
      is_system: true
    }

    render(
      <ManageAgentAccessModal
        agent={systemAgent}
        groups={mockGroups}
        onClose={mockOnClose}
        onGrantToGroup={mockOnGrantToGroup}
        onRevokeFromGroup={mockOnRevokeFromGroup}
        onToggle={mockOnToggle}

      />
    )

    expect(screen.getByText(/System Agent/)).toBeInTheDocument()
    expect(screen.getByText(/always enabled/)).toBeInTheDocument()
  })

  it('calls onClose when close button is clicked', () => {
    render(
      <ManageAgentAccessModal
        agent={mockAgent}
        groups={mockGroups}
        onClose={mockOnClose}
        onGrantToGroup={mockOnGrantToGroup}
        onRevokeFromGroup={mockOnRevokeFromGroup}
        onToggle={mockOnToggle}

      />
    )

    const closeButton = document.querySelector('.modal-close')
    fireEvent.click(closeButton)

    expect(mockOnClose).toHaveBeenCalled()
  })
})
