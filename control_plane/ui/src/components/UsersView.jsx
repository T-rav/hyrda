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

      <table className="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Status</th>
            <th>Admin</th>
            <th>Last Synced</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map(user => (
            <tr key={user.id}>
              <td>{user.full_name}</td>
              <td>{user.email}</td>
              <td>
                <span className={`status-badge ${user.is_active ? 'status-active' : 'status-inactive'}`}>
                  {user.is_active ? 'Active' : 'Inactive'}
                </span>
              </td>
              <td>{user.is_admin ? 'Yes' : 'No'}</td>
              <td>{user.last_synced_at ? new Date(user.last_synced_at).toLocaleDateString() : 'Never'}</td>
              <td>
                <button
                  onClick={() => setSelectedUser(user)}
                  className="btn-secondary btn-small"
                >
                  Manage Permissions
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

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
