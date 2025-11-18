import React, { useState } from 'react'
import { X, Plus, Trash2 } from 'lucide-react'

function ManageGroupUsersModal({ group, users, onClose, onAddUser, onRemoveUser }) {
  const [searchTerm, setSearchTerm] = useState('')

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
            {filteredUsers.map(user => (
              <div key={user.id} className="user-selection-item">
                <div>
                  <div className="user-name">{user.full_name}</div>
                  <div className="user-email">{user.email}</div>
                </div>
                <div>
                  <button
                    onClick={() => onAddUser(user.slack_user_id)}
                    className="btn-sm btn-primary"
                  >
                    <Plus size={14} />
                    Add
                  </button>
                  <button
                    onClick={() => onRemoveUser(user.slack_user_id)}
                    className="btn-sm btn-danger"
                    style={{ marginLeft: '0.5rem' }}
                  >
                    <Trash2 size={14} />
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="modal-actions">
          <button onClick={onClose} className="btn-primary">
            Done
          </button>
        </div>
      </div>
    </div>
  )
}

export default ManageGroupUsersModal
