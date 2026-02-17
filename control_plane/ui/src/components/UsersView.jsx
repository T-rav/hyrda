import React, { useState } from 'react'
import { Users, RefreshCw, Shield, ChevronDown } from 'lucide-react'
import ManageUserGroupsModal from './ManageUserGroupsModal'

function UsersView({
  users,
  totalUsers,
  hasMore,
  loadingMore,
  groups,
  onRefresh,
  onSync,
  syncing,
  onLoadMore,
  onAddUserToGroup,
  onRemoveUserFromGroup,
  onUpdateAdminStatus,
  currentUserEmail
}) {
  const [selectedUser, setSelectedUser] = useState(null)
  const [updatingAdmin, setUpdatingAdmin] = useState(null)

  const handleAdminToggle = async (user) => {
    setUpdatingAdmin(user.id)
    try {
      await onUpdateAdminStatus(user.id, !user.is_admin)
    } finally {
      setUpdatingAdmin(null)
    }
  }

  // Check if there are any admins
  const hasAdmins = users.some(u => u.is_admin)
  // Check if current user is admin
  const currentUser = users.find(u => u.email === currentUserEmail)
  const isCurrentUserAdmin = currentUser?.is_admin || false

  const remainingUsers = totalUsers - users.length

  return (
    <div className="content-section">
      <div className="section-header">
        <h2>Users ({users.length} of {totalUsers})</h2>
        <div>
          <button onClick={onRefresh} className="btn btn-outline-secondary">
            <RefreshCw size={16} />
            Refresh
          </button>
          <button
            onClick={onSync}
            className="btn btn-outline-primary"
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
              <td>
                <button
                  onClick={() => handleAdminToggle(user)}
                  className={`btn btn-small ${user.is_admin ? 'btn-outline-danger' : 'btn-outline-primary'}`}
                  disabled={updatingAdmin === user.id || (!hasAdmins ? false : !isCurrentUserAdmin)}
                  title={!hasAdmins ? 'Create first admin' : (isCurrentUserAdmin ? 'Toggle admin status' : 'Only admins can change admin status')}
                  style={{ minWidth: '80px' }}
                >
                  {updatingAdmin === user.id ? '...' : (user.is_admin ? 'Remove Admin' : 'Make Admin')}
                </button>
              </td>
              <td>{user.last_synced_at ? new Date(user.last_synced_at).toLocaleDateString() : 'Never'}</td>
              <td>
                <button
                  onClick={() => setSelectedUser(user)}
                  className="btn btn-outline-secondary btn-small"
                >
                  <Shield size={14} />
                  Manage Groups
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Load More Button */}
      {hasMore && (
        <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
          <button
            onClick={onLoadMore}
            disabled={loadingMore}
            className="btn btn-outline-primary"
            style={{ minWidth: '200px' }}
          >
            {loadingMore ? (
              <>
                <RefreshCw size={16} className="spinning" />
                Loading...
              </>
            ) : (
              <>
                <ChevronDown size={16} />
                Load 50 more ({remainingUsers} remaining)
              </>
            )}
          </button>
        </div>
      )}

      {users.length === 0 && (
        <div className="empty-state">
          <Users size={48} />
          <p>No users synced yet</p>
          <button onClick={onSync} className="btn btn-outline-primary" disabled={syncing}>
            Sync Users from Slack
          </button>
        </div>
      )}

      {users.length > 0 && !hasAdmins && (
        <div style={{
          marginTop: '1rem',
          padding: '1rem',
          background: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)',
          borderRadius: '0.5rem',
          border: '2px solid #fbbf24'
        }}>
          <p style={{ margin: 0, fontSize: '0.875rem', color: '#78350f', fontWeight: '600' }}>
            ⚠️ <strong>No admins configured!</strong> Click "Make Admin" on any user to create the first admin. After that, only admins can manage admin status.
          </p>
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
