import React from 'react'

function UserCard({ user, agents, onGrantAgent, onRevokeAgent, isSelected, onClick }) {
  return (
    <div className={`user-card ${isSelected ? 'selected' : ''}`} onClick={onClick}>
      <div className="user-header">
        <div>
          <h3>{user.full_name}</h3>
          <p className="user-email">{user.email}</p>
        </div>
        <div className="user-badges">
          {user.is_admin && <span className="badge admin">Admin</span>}
          {user.is_active ? (
            <span className="badge active">Active</span>
          ) : (
            <span className="badge inactive">Inactive</span>
          )}
        </div>
      </div>
      <div className="user-footer">
        <span className="user-id">{user.slack_user_id}</span>
        {user.last_synced_at && (
          <span className="user-sync">
            Synced: {new Date(user.last_synced_at).toLocaleDateString()}
          </span>
        )}
      </div>
    </div>
  )
}

export default UserCard
