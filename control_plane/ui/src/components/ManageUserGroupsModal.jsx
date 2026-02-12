import React, { useState, useEffect } from 'react'
import { X, Plus, Trash2, Users as UsersIcon, Shield } from 'lucide-react'

function ManageUserGroupsModal({ user, groups, onClose, onAddToGroup, onRemoveFromGroup }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [localGroups, setLocalGroups] = useState(new Set())

  // Sync local groups with user.groups prop
  useEffect(() => {
    setLocalGroups(new Set((user.groups || []).map(g => g.group_name)))
  }, [user.groups])

  const handleAdd = async (groupName, userId) => {
    // Optimistically update UI
    setLocalGroups(prev => new Set([...prev, groupName]))
    try {
      await onAddToGroup(groupName, userId)
    } catch (error) {
      // Revert on error
      setLocalGroups(prev => {
        const next = new Set(prev)
        next.delete(groupName)
        return next
      })
    }
  }

  const handleRemove = async (groupName, userId) => {
    // Optimistically update UI
    setLocalGroups(prev => {
      const next = new Set(prev)
      next.delete(groupName)
      return next
    })
    try {
      await onRemoveFromGroup(groupName, userId)
    } catch (error) {
      // Revert on error
      setLocalGroups(prev => new Set([...prev, groupName]))
    }
  }

  const filteredGroups = groups.filter(group =>
    (group.display_name || group.group_name).toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content large" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Manage Groups: {user.full_name}</h2>
          <button onClick={onClose} className="modal-close">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <div style={{ padding: '1rem', background: '#f8fafc', borderRadius: '0.5rem', border: '1px solid #e2e8f0', marginBottom: '1rem' }}>
            <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>
              💡 Add or remove this user from groups. The user will automatically inherit agent permissions from their group memberships.
            </p>
          </div>

          <div className="form-group" style={{ padding: '0 1rem 1rem' }}>
            <input
              type="text"
              placeholder="Search groups..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="search-input"
            />
          </div>

          <div className="user-selection-list">
            {filteredGroups.map(group => {
              const isMember = localGroups.has(group.group_name)
              const isSystemGroup = group.group_name === 'all_users'

              return (
                <div key={group.group_name} className="user-selection-item">
                  <div>
                    <div className="user-name">
                      {group.display_name || group.group_name}
                      {isMember && (
                        <span className="badge-in-group">
                          <Shield size={12} /> Member
                        </span>
                      )}
                    </div>
                    <div className="user-email">{group.description || `${group.user_count} users`}</div>
                  </div>
                  <div>
                    {!isMember && !isSystemGroup && (
                      <button
                        onClick={() => handleAdd(group.group_name, user.slack_user_id)}
                        className="btn btn-sm btn-outline-primary"
                      >
                        <Plus size={14} />
                        Add
                      </button>
                    )}
                    {isMember && !isSystemGroup && (
                      <button
                        onClick={() => handleRemove(group.group_name, user.slack_user_id)}
                        className="btn btn-sm btn-outline-danger"
                      >
                        <Trash2 size={14} />
                        Remove
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="modal-actions">
          <button onClick={onClose} className="btn btn-outline-primary">
            Done
          </button>
        </div>
      </div>
    </div>
  )
}

export default ManageUserGroupsModal
