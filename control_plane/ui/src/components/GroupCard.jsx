import React from 'react'
import { Users, UserPlus, Bot } from 'lucide-react'

function GroupCard({ group, onManageUsers, onManageAgents }) {
  const users = group.users || []
  const displayedUsers = users.slice(0, 3)
  const remainingCount = users.length - displayedUsers.length

  return (
    <div className="group-card">
      <div className="group-header">
        <div>
          <h3>{group.display_name || group.group_name}</h3>
          <p className="group-id">@{group.group_name}</p>
        </div>
        <div className="group-stats">
          <span className="stat-badge users">
            <Users size={14} />
            {group.user_count || 0} {group.user_count === 1 ? 'user' : 'users'}
          </span>
        </div>
      </div>

      {group.description && (
        <p className="group-description">{group.description}</p>
      )}

      {/* Display users list */}
      {users.length > 0 && (
        <div className="group-users-list">
          {displayedUsers.map((user, index) => (
            <div key={user.slack_user_id} className="user-chip">
              <span className="user-chip-name">{user.full_name}</span>
              <span className="user-chip-email">{user.email}</span>
            </div>
          ))}
          {remainingCount > 0 && (
            <div className="user-chip user-chip-more">
              +{remainingCount} more
            </div>
          )}
        </div>
      )}

      {users.length === 0 && (
        <div className="group-empty-state">
          <Users size={16} style={{ opacity: 0.3 }} />
          <span>No users in this group</span>
        </div>
      )}

      <div className="group-footer">
        <button className="btn-link" onClick={() => onManageUsers(group)}>
          <UserPlus size={16} />
          Manage Users
        </button>
        <button className="btn-link" onClick={() => onManageAgents(group)}>
          <Bot size={16} />
          Manage Agents
        </button>
      </div>
    </div>
  )
}

export default GroupCard
