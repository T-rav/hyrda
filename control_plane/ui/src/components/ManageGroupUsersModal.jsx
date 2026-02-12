import React, { useState, useEffect } from 'react'
import { X, Plus, Trash2, Shield } from 'lucide-react'

function ManageGroupUsersModal({ group, users, onClose, onAddUser, onRemoveUser }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [localUserIds, setLocalUserIds] = useState(new Set())

  // Check if this is a system group
  const isSystemGroup = group.group_name === 'all_users'

  // Sync local user IDs with group.users prop
  useEffect(() => {
    setLocalUserIds(new Set((group.users || []).map(u => u.slack_user_id)))
  }, [group.users])

  const handleAdd = async (userId) => {
    // Optimistically update UI
    setLocalUserIds(prev => new Set([...prev, userId]))
    try {
      await onAddUser(userId)
    } catch (error) {
      // Revert on error
      setLocalUserIds(prev => {
        const next = new Set(prev)
        next.delete(userId)
        return next
      })
    }
  }

  const handleRemove = async (userId) => {
    // Optimistically update UI
    setLocalUserIds(prev => {
      const next = new Set(prev)
      next.delete(userId)
      return next
    })
    try {
      await onRemoveUser(userId)
    } catch (error) {
      // Revert on error
      setLocalUserIds(prev => new Set([...prev, userId]))
    }
  }

  const filteredUsers = users.filter(user =>
    user.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.email.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content large" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Manage Users: {group.display_name}</h2>
          <button onClick={onClose} className="modal-close">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {isSystemGroup && (
            <div style={{ padding: '1rem', background: '#fef3c7', borderRadius: '0.5rem', border: '1px solid #fbbf24', marginBottom: '1rem' }}>
              <p style={{ margin: 0, fontSize: '0.875rem', color: '#92400e' }}>
                ⚠️ System group: All active users are automatically included and cannot be manually modified.
              </p>
            </div>
          )}

          <div className="form-group">
            <input
              type="text"
              placeholder="Search users..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="search-input"
            />
          </div>

          <div className="user-selection-list">
            {filteredUsers.map(user => {
              const isInGroup = localUserIds.has(user.slack_user_id)

              return (
                <div key={user.id} className="user-selection-item">
                  <div>
                    <div className="user-name">
                      {user.full_name}
                      {isInGroup && <span className="badge-in-group">In Group</span>}
                    </div>
                    <div className="user-email">{user.email}</div>
                  </div>
                  <div>
                    {!isSystemGroup && !isInGroup && (
                      <button
                        onClick={() => handleAdd(user.slack_user_id)}
                        className="btn-sm btn-outline-primary"
                      >
                        <Plus size={14} />
                        Add
                      </button>
                    )}
                    {!isSystemGroup && isInGroup && (
                      <button
                        onClick={() => handleRemove(user.slack_user_id)}
                        className="btn-sm btn-outline-danger"
                      >
                        <Trash2 size={14} />
                        Remove
                      </button>
                    )}
                    {isSystemGroup && isInGroup && (
                      <span className="badge-in-group">
                        <Shield size={12} /> Auto-added
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="modal-actions">
          <button onClick={onClose} className="btn-outline-primary">
            Done
          </button>
        </div>
      </div>
    </div>
  )
}

export default ManageGroupUsersModal
