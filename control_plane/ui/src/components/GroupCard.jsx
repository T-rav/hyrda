import React from 'react'
import { Users, UserPlus, Bot } from 'lucide-react'

function GroupCard({ group, onManageUsers, onManageAgents }) {
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
            {group.user_count || 0} users
          </span>
        </div>
      </div>

      {group.description && (
        <p className="group-description">{group.description}</p>
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
