import React, { useState } from 'react'
import { Users, RefreshCw, Plus } from 'lucide-react'
import GroupCard from './GroupCard'
import CreateGroupModal from './CreateGroupModal'
import EditGroupModal from './EditGroupModal'
import ManageGroupUsersModal from './ManageGroupUsersModal'
import PermissionModal from './PermissionModal'

function GroupsView({
  groups,
  users,
  agents,
  onRefresh,
  showCreateGroup,
  setShowCreateGroup,
  onCreateGroup,
  onUpdateGroup,
  onAddUserToGroup,
  onRemoveUserFromGroup,
  onDeleteGroup,
  onGrantAgent,
  onRevokeAgent,
  selectedGroup,
  setSelectedGroup
}) {
  const [showEditGroup, setShowEditGroup] = useState(false)
  const [showManageUsers, setShowManageUsers] = useState(false)
  const [showManageAgents, setShowManageAgents] = useState(false)
  const [groupAgentPermissions, setGroupAgentPermissions] = useState([])

  const handleEditGroup = (group) => {
    setSelectedGroup(group)
    setShowEditGroup(true)
  }

  const handleUpdateGroup = (groupName, groupData) => {
    onUpdateGroup(groupName, groupData)
    setShowEditGroup(false)
    setSelectedGroup(null)
  }

  const handleManageUsers = (group) => {
    setSelectedGroup(group)
    setShowManageUsers(true)
  }

  const handleManageAgents = async (group) => {
    setSelectedGroup(group)

    // Fetch agents that this group has access to
    try {
      const response = await fetch(`/api/groups/${group.group_name}/agents`)
      if (response.ok) {
        const data = await response.json()
        setGroupAgentPermissions(data.agent_names || [])
      }
    } catch (err) {
      console.error('Error fetching group agent permissions:', err)
      setGroupAgentPermissions([])
    }

    setShowManageAgents(true)
  }

  return (
    <div className="content-section">
      <div className="section-header">
        <h2>Permission Groups ({groups.length})</h2>
        <div>
          <button onClick={onRefresh} className="btn btn-outline-secondary">
            <RefreshCw size={16} />
            Refresh
          </button>
          <button
            onClick={() => setShowCreateGroup(true)}
            className="btn btn-outline-primary"
            style={{ marginLeft: '0.5rem' }}
          >
            <Plus size={16} />
            Create Group
          </button>
        </div>
      </div>

      {showCreateGroup && (
        <CreateGroupModal
          onClose={() => setShowCreateGroup(false)}
          onCreate={onCreateGroup}
        />
      )}

      {showEditGroup && selectedGroup && (
        <EditGroupModal
          group={selectedGroup}
          onClose={() => {
            setShowEditGroup(false)
            setSelectedGroup(null)
          }}
          onUpdate={handleUpdateGroup}
        />
      )}

      {showManageUsers && selectedGroup && (
        <ManageGroupUsersModal
          group={selectedGroup}
          users={users}
          onClose={() => {
            setShowManageUsers(false)
            setSelectedGroup(null)
            onRefresh()
          }}
          onAddUser={(userId) => onAddUserToGroup(selectedGroup.group_name, userId)}
          onRemoveUser={(userId) => onRemoveUserFromGroup(selectedGroup.group_name, userId)}
        />
      )}

      {showManageAgents && selectedGroup && (
        <PermissionModal
          title={`Manage Agents: ${selectedGroup.display_name}`}
          agents={agents}
          userPermissions={groupAgentPermissions}
          onClose={() => {
            setShowManageAgents(false)
            setSelectedGroup(null)
            setGroupAgentPermissions([])
          }}
          onGrant={(agentName) => {
            onGrantAgent(selectedGroup.group_name, agentName)
            // Add to local state immediately for UI update
            setGroupAgentPermissions([...groupAgentPermissions, agentName])
          }}
          onRevoke={(agentName) => {
            onRevokeAgent(selectedGroup.group_name, agentName)
            // Remove from local state immediately for UI update
            setGroupAgentPermissions(groupAgentPermissions.filter(name => name !== agentName))
          }}
        />
      )}

      <div className="groups-list">
        {groups.map(group => (
          <GroupCard
            key={group.group_name}
            group={group}
            onEdit={handleEditGroup}
            onManageUsers={handleManageUsers}
            onManageAgents={handleManageAgents}
            onDelete={onDeleteGroup}
          />
        ))}
      </div>

      {groups.length === 0 && !showCreateGroup && (
        <div className="empty-state">
          <Users size={48} />
          <p>No groups created yet</p>
          <button onClick={() => setShowCreateGroup(true)} className="btn btn-outline-primary">
            Create Your First Group
          </button>
        </div>
      )}
    </div>
  )
}

export default GroupsView
