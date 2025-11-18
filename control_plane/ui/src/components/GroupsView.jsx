import React, { useState } from 'react'
import { Users, RefreshCw, Plus } from 'lucide-react'
import GroupCard from './GroupCard'
import CreateGroupModal from './CreateGroupModal'
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
  onAddUserToGroup,
  onRemoveUserFromGroup,
  onGrantAgent,
  onRevokeAgent,
  selectedGroup,
  setSelectedGroup
}) {
  const [showManageUsers, setShowManageUsers] = useState(false)
  const [showManageAgents, setShowManageAgents] = useState(false)

  const handleManageUsers = (group) => {
    setSelectedGroup(group)
    setShowManageUsers(true)
  }

  const handleManageAgents = (group) => {
    setSelectedGroup(group)
    setShowManageAgents(true)
  }

  return (
    <div className="content-section">
      <div className="section-header">
        <h2>Permission Groups ({groups.length})</h2>
        <div>
          <button onClick={onRefresh} className="btn-secondary">
            <RefreshCw size={16} />
            Refresh
          </button>
          <button
            onClick={() => setShowCreateGroup(true)}
            className="btn-primary"
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
          onClose={() => {
            setShowManageAgents(false)
            setSelectedGroup(null)
          }}
          onGrant={(agentName) => onGrantAgent(selectedGroup.group_name, agentName)}
          onRevoke={(agentName) => onRevokeAgent(selectedGroup.group_name, agentName)}
        />
      )}

      <div className="groups-list">
        {groups.map(group => (
          <GroupCard
            key={group.group_name}
            group={group}
            onManageUsers={handleManageUsers}
            onManageAgents={handleManageAgents}
          />
        ))}
      </div>

      {groups.length === 0 && !showCreateGroup && (
        <div className="empty-state">
          <Users size={48} />
          <p>No groups created yet</p>
          <button onClick={() => setShowCreateGroup(true)} className="btn-primary">
            Create Your First Group
          </button>
        </div>
      )}
    </div>
  )
}

export default GroupsView
