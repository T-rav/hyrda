import React from 'react'
import { Users, UserPlus, Bot, Trash2, Edit } from 'lucide-react'

function GroupCard({ group, onEdit, onManageUsers, onManageAgents, onDelete }) {
  const handleDelete = () => {
    if (window.confirm(`Are you sure you want to delete the group "${group.display_name || group.group_name}"? This will remove all user memberships and agent permissions.`)) {
      onDelete(group.group_name)
    }
  }
  const users = group.users || []
  const displayedUsers = users.slice(0, 3)
  const remainingCount = users.length - displayedUsers.length

  return (
    <div className="group-card">
      <div className="group-header">
        <div>
          <h3>{group.display_name || group.group_name}</h3>
          {group.group_name === 'all_users' && (
            <span className="stat-badge" style={{
              background: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)',
              color: '#92400e',
              border: '1px solid #fbbf24',
              fontSize: '0.7rem',
              marginTop: '0.25rem'
            }}>
              System Group
            </span>
          )}
        </div>
        <div className="group-stats">
          <span className="stat-badge users">
            <Users size={14} />
            {group.user_count} {group.user_count === 1 ? 'user' : 'users'}
          </span>
        </div>
      </div>

      {group.description && (
        <p className="group-description">{group.description}</p>
      )}

      <div className="group-footer">
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-sm btn-outline-primary" onClick={() => onEdit(group)}>
            <Edit size={16} />
            Edit
          </button>
          <button className="btn btn-sm btn-outline-primary" onClick={() => onManageUsers(group)}>
            <UserPlus size={16} />
            Manage Users
          </button>
          <button className="btn btn-sm btn-outline-primary" onClick={() => onManageAgents(group)}>
            <Bot size={16} />
            Manage Agents
          </button>
        </div>
        {group.group_name !== 'all_users' && (
          <button
            className="btn btn-sm btn-outline-danger"
            onClick={handleDelete}
            title="Delete group"
          >
            <Trash2 size={16} />
            Delete
          </button>
        )}
      </div>
    </div>
  )
}

export default GroupCard
