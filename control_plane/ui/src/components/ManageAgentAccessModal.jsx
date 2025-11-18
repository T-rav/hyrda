import React, { useState } from 'react'
import { Users, X, Plus, Trash2 } from 'lucide-react'

function ManageAgentAccessModal({ agent, users, groups, onClose, onGrantToUser, onRevokeFromUser, onGrantToGroup, onRevokeFromGroup }) {
  const [activeSection, setActiveSection] = useState('users')

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content large" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Manage Access: /{agent.name}</h2>
          <button onClick={onClose} className="modal-close">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <div className="section-tabs">
            <button
              className={activeSection === 'users' ? 'active' : ''}
              onClick={() => setActiveSection('users')}
            >
              <Users size={16} />
              Users
            </button>
            <button
              className={activeSection === 'groups' ? 'active' : ''}
              onClick={() => setActiveSection('groups')}
            >
              <Users size={16} />
              Groups
            </button>
          </div>

          {activeSection === 'users' && (
            <div className="user-selection-list">
              <h3 style={{ padding: '1rem', margin: 0, borderBottom: '1px solid #e2e8f0' }}>
                Grant or revoke access for individual users
              </h3>
              {users.map(user => (
                <div key={user.id} className="user-selection-item">
                  <div>
                    <div className="user-name">{user.full_name}</div>
                    <div className="user-email">{user.email}</div>
                  </div>
                  <div>
                    <button
                      onClick={() => onGrantToUser(user.slack_user_id, agent.name)}
                      className="btn-sm btn-primary"
                    >
                      <Plus size={14} />
                      Grant
                    </button>
                    <button
                      onClick={() => onRevokeFromUser(user.slack_user_id, agent.name)}
                      className="btn-sm btn-danger"
                      style={{ marginLeft: '0.5rem' }}
                    >
                      <Trash2 size={14} />
                      Revoke
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeSection === 'groups' && (
            <div className="user-selection-list">
              <h3 style={{ padding: '1rem', margin: 0, borderBottom: '1px solid #e2e8f0' }}>
                Grant or revoke access for groups
              </h3>
              {groups.map(group => (
                <div key={group.group_name} className="user-selection-item">
                  <div>
                    <div className="user-name">{group.display_name || group.group_name}</div>
                    <div className="user-email">@{group.group_name} • {group.user_count} users</div>
                  </div>
                  <div>
                    <button
                      onClick={() => onGrantToGroup(group.group_name, agent.name)}
                      className="btn-sm btn-primary"
                    >
                      <Plus size={14} />
                      Grant
                    </button>
                    <button
                      onClick={() => onRevokeFromGroup(group.group_name, agent.name)}
                      className="btn-sm btn-danger"
                      style={{ marginLeft: '0.5rem' }}
                    >
                      <Trash2 size={14} />
                      Revoke
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
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

export default ManageAgentAccessModal
