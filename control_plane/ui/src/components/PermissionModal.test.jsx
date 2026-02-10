import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import PermissionModal from './PermissionModal'

describe('PermissionModal', () => {
  const mockAgents = [
    { name: 'agent1', description: 'First agent' },
    { name: 'agent2', description: 'Second agent' },
    { name: 'agent3', description: 'Third agent' }
  ]

  const mockPermissions = ['agent1']

  const mockOnClose = jest.fn()
  const mockOnGrant = jest.fn()
  const mockOnRevoke = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders correctly with title and agents', () => {
    render(
      <PermissionModal
        title="Manage Permissions"
        agents={mockAgents}
        userPermissions={mockPermissions}
        onClose={mockOnClose}
        onGrant={mockOnGrant}
        onRevoke={mockOnRevoke}
      />
    )

    expect(screen.getByText('Manage Permissions')).toBeInTheDocument()
    expect(screen.getByText('/agent1')).toBeInTheDocument()
    expect(screen.getByText('/agent2')).toBeInTheDocument()
  })

  it('shows Has Access badge for agents with permissions', () => {
    render(
      <PermissionModal
        title="Manage Permissions"
        agents={mockAgents}
        userPermissions={mockPermissions}
        onClose={mockOnClose}
        onGrant={mockOnGrant}
        onRevoke={mockOnRevoke}
      />
    )

    expect(screen.getByText('Has Access')).toBeInTheDocument()
  })

  it('shows Grant button for agents without permissions', () => {
    render(
      <PermissionModal
        title="Manage Permissions"
        agents={mockAgents}
        userPermissions={mockPermissions}
        onClose={mockOnClose}
        onGrant={mockOnGrant}
        onRevoke={mockOnRevoke}
      />
    )

    const grantButtons = screen.getAllByText('Grant')
    expect(grantButtons.length).toBeGreaterThan(0)
  })

  it('shows Revoke button for agents with permissions', () => {
    render(
      <PermissionModal
        title="Manage Permissions"
        agents={mockAgents}
        userPermissions={mockPermissions}
        onClose={mockOnClose}
        onGrant={mockOnGrant}
        onRevoke={mockOnRevoke}
      />
    )

    expect(screen.getByText('Revoke')).toBeInTheDocument()
  })

  it('calls onGrant when Grant button is clicked', async () => {
    mockOnGrant.mockResolvedValueOnce()

    render(
      <PermissionModal
        title="Manage Permissions"
        agents={mockAgents}
        userPermissions={mockPermissions}
        onClose={mockOnClose}
        onGrant={mockOnGrant}
        onRevoke={mockOnRevoke}
      />
    )

    const grantButton = screen.getAllByText('Grant')[0]
    fireEvent.click(grantButton)

    await waitFor(() => {
      expect(mockOnGrant).toHaveBeenCalledWith('agent2')
    })
  })

  it('calls onRevoke when Revoke button is clicked', async () => {
    mockOnRevoke.mockResolvedValueOnce()

    render(
      <PermissionModal
        title="Manage Permissions"
        agents={mockAgents}
        userPermissions={mockPermissions}
        onClose={mockOnClose}
        onGrant={mockOnGrant}
        onRevoke={mockOnRevoke}
      />
    )

    const revokeButton = screen.getByText('Revoke')
    fireEvent.click(revokeButton)

    await waitFor(() => {
      expect(mockOnRevoke).toHaveBeenCalledWith('agent1')
    })
  })

  it('optimistically updates UI when Grant is clicked', async () => {
    mockOnGrant.mockResolvedValueOnce()

    render(
      <PermissionModal
        title="Manage Permissions"
        agents={mockAgents}
        userPermissions={mockPermissions}
        onClose={mockOnClose}
        onGrant={mockOnGrant}
        onRevoke={mockOnRevoke}
      />
    )

    // Initially agent2 shows Grant button
    const agent2Section = screen.getByText('/agent2').closest('.user-selection-item')
    expect(agent2Section).toHaveTextContent('Grant')

    // Click Grant
    const grantButton = screen.getAllByText('Grant')[0]
    fireEvent.click(grantButton)

    // UI should immediately show Revoke (optimistic update)
    await waitFor(() => {
      expect(agent2Section).toHaveTextContent('Revoke')
    })
  })

  it('optimistically updates UI when Revoke is clicked', async () => {
    mockOnRevoke.mockResolvedValueOnce()

    render(
      <PermissionModal
        title="Manage Permissions"
        agents={mockAgents}
        userPermissions={mockPermissions}
        onClose={mockOnClose}
        onGrant={mockOnGrant}
        onRevoke={mockOnRevoke}
      />
    )

    // Initially agent1 shows Revoke button
    const agent1Section = screen.getByText('/agent1').closest('.user-selection-item')
    expect(agent1Section).toHaveTextContent('Revoke')

    // Click Revoke
    const revokeButton = screen.getByText('Revoke')
    fireEvent.click(revokeButton)

    // UI should immediately show Grant (optimistic update)
    await waitFor(() => {
      expect(agent1Section).toHaveTextContent('Grant')
    })
  })

  it('reverts UI on grant error', async () => {
    mockOnGrant.mockRejectedValueOnce(new Error('Failed to grant'))

    render(
      <PermissionModal
        title="Manage Permissions"
        agents={mockAgents}
        userPermissions={mockPermissions}
        onClose={mockOnClose}
        onGrant={mockOnGrant}
        onRevoke={mockOnRevoke}
      />
    )

    // Click Grant
    const grantButton = screen.getAllByText('Grant')[0]
    fireEvent.click(grantButton)

    // Wait for error handling
    await waitFor(() => {
      expect(mockOnGrant).toHaveBeenCalled()
    })

    // UI should revert to Grant button
    await waitFor(() => {
      const agent2Section = screen.getByText('/agent2').closest('.user-selection-item')
      expect(agent2Section).toHaveTextContent('Grant')
    })
  })

  it('filters agents based on search term', () => {
    render(
      <PermissionModal
        title="Manage Permissions"
        agents={mockAgents}
        userPermissions={mockPermissions}
        onClose={mockOnClose}
        onGrant={mockOnGrant}
        onRevoke={mockOnRevoke}
      />
    )

    const searchInput = screen.getByPlaceholderText('Search agents...')
    fireEvent.change(searchInput, { target: { value: 'agent2' } })

    expect(screen.getByText('/agent2')).toBeInTheDocument()
    expect(screen.queryByText('/agent3')).not.toBeInTheDocument()
  })

  it('calls onClose when close button is clicked', () => {
    render(
      <PermissionModal
        title="Manage Permissions"
        agents={mockAgents}
        userPermissions={mockPermissions}
        onClose={mockOnClose}
        onGrant={mockOnGrant}
        onRevoke={mockOnRevoke}
      />
    )

    const closeButton = document.querySelector('.modal-close')
    fireEvent.click(closeButton)

    expect(mockOnClose).toHaveBeenCalled()
  })

  it('calls onClose when Close button is clicked', () => {
    render(
      <PermissionModal
        title="Manage Permissions"
        agents={mockAgents}
        userPermissions={mockPermissions}
        onClose={mockOnClose}
        onGrant={mockOnGrant}
        onRevoke={mockOnRevoke}
      />
    )

    const closeButton = screen.getByText('Close')
    fireEvent.click(closeButton)

    expect(mockOnClose).toHaveBeenCalled()
  })
})
