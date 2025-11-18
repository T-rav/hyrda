import React from 'react'
import { Users, RefreshCw } from 'lucide-react'
import UserCard from './UserCard'
import PermissionModal from './PermissionModal'

function UsersView({ users, agents, onRefresh, onSync, syncing, onGrantAgent, onRevokeAgent, selectedUser, setSelectedUser }) {
  return (
    <div className="content-section">
      <div className="section-header">
        <h2>Users ({users.length})</h2>
        <div>
          <button onClick={onRefresh} className="btn-secondary">
            <RefreshCw size={16} />
            Refresh
          </button>
          <button
            onClick={onSync}
            className="btn-primary"
            disabled={syncing}
            style={{ marginLeft: '0.5rem' }}
          >
            <RefreshCw size={16} className={syncing ? 'spinning' : ''} />
            Sync from Slack
          </button>
        </div>
      </div>

      <div className="users-list">
        {users.map(user => (
          <UserCard
            key={user.id}
            user={user}
            agents={agents}
            onGrantAgent={onGrantAgent}
            onRevokeAgent={onRevokeAgent}
            isSelected={selectedUser?.id === user.id}
            onClick={() => setSelectedUser(user)}
          />
        ))}
      </div>

      {users.length === 0 && (
        <div className="empty-state">
          <Users size={48} />
          <p>No users synced yet</p>
          <button onClick={onSync} className="btn-primary" disabled={syncing}>
            Sync Users from Slack
          </button>
        </div>
      )}

      {selectedUser && (
        <PermissionModal
          title={`Manage Permissions: ${selectedUser.full_name}`}
          agents={agents}
          onClose={() => setSelectedUser(null)}
          onGrant={(agentName) => onGrantAgent(selectedUser.slack_user_id, agentName)}
          onRevoke={(agentName) => onRevokeAgent(selectedUser.slack_user_id, agentName)}
        />
      )}
    </div>
  )
}

export default UsersView
