import React, { useState } from 'react'
import { Users, RefreshCw, Shield } from 'lucide-react'
import ManageUserGroupsModal from './ManageUserGroupsModal'

function UsersView({ users, groups, onRefresh, onSync, syncing, onAddUserToGroup, onRemoveUserFromGroup }) {
  const [selectedUser, setSelectedUser] = useState(null)

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
            <th>Groups</th>
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
                {user.groups && user.groups.length > 0 ? (
                  <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
                    {user.groups.map(group => (
                      <span key={group.group_name} className="stat-badge users" style={{ fontSize: '0.75rem' }}>
                        {group.display_name || group.group_name}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span style={{ color: '#94a3b8', fontSize: '0.875rem' }}>No groups</span>
                )}
              </td>
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
                  <Shield size={14} />
                  Manage Groups
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

      <div style={{ marginTop: '2rem', padding: '1rem', background: '#f8fafc', borderRadius: '0.5rem', border: '1px solid #e2e8f0' }}>
        <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>
          💡 <strong>Agent permissions are managed at the group level.</strong> Add users to groups, then grant agent access to those groups in the Groups or Agents tabs.
        </p>
      </div>

      {selectedUser && (
        <ManageUserGroupsModal
          user={selectedUser}
          groups={groups}
          onClose={() => setSelectedUser(null)}
          onAddToGroup={onAddUserToGroup}
          onRemoveFromGroup={onRemoveUserFromGroup}
        />
      )}
    </div>
  )
}

export default UsersView
