import React, { useState } from 'react'
import { Users, X, Plus, Trash2, Shield } from 'lucide-react'

function ManageAgentAccessModal({ agent, groups, onClose, onGrantToGroup, onRevokeFromGroup, onToggle, onDelete }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)

  // Create set of authorized group names
  const authorizedGroupNames = new Set(agent.authorized_group_names || [])

  // For system agents, only show all_users group
  const filteredGroups = groups
    .filter(group => !agent.is_system || group.group_name === 'all_users')
    .filter(group =>
      (group.display_name || group.group_name).toLowerCase().includes(searchTerm.toLowerCase())
    )

  const handleToggle = () => {
    onToggle(agent.name)
  }

  const handleDelete = async () => {
    try {
      setDeleting(true)
      await onDelete(agent.name)
      onClose() // Close modal after successful deletion
    } catch (err) {
      // Error is handled by useAgents hook with toast
      setDeleting(false)
      setShowDeleteConfirm(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content large" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Manage Group Access: /{agent.name}</h2>
          <button onClick={onClose} className="modal-close">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {agent.is_system && (
            <div className="system-agent-banner">
              <div className="system-agent-banner-header">
                <Shield size={16} />
                <strong>System Agent</strong>
              </div>
              <p>
                This agent is always enabled and accessible to all users. It cannot be disabled or restricted.
              </p>
            </div>
          )}

          {!agent.is_system && (
            <div className="agent-status-section">
              <div className="agent-status-info">
                <h3>Slack Visibility</h3>
                <p>Control whether this agent is visible in Slack (API enforcement not implemented yet)</p>
              </div>
              <div className="toggle-switch" onClick={handleToggle}>
                <input
                  type="checkbox"
                  checked={agent.is_public}
                  onChange={() => {}}
                  className="toggle-checkbox"
                />
                <span className="toggle-slider"></span>
                <span className="toggle-label">
                  {agent.is_public ? 'Enabled' : 'Disabled'}
                </span>
              </div>
            </div>
          )}

          {!agent.is_system && (
            <>
              <div className="info-box">
                <p>
                  💡 Grant or revoke access to groups. Users in these groups will automatically have access to this agent.
                </p>
              </div>

              <div className="form-group search-group">
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
              const hasAccess = authorizedGroupNames.has(group.group_name)
              const isSystemGroup = group.group_name === 'all_users'

              return (
                <div key={group.group_name} className="user-selection-item">
                  <div>
                    <div className="user-name">{group.display_name || group.group_name}</div>
                    <div className="badge-container">
                      {isSystemGroup && (
                        <span className="stat-badge system">
                          System
                        </span>
                      )}
                      {hasAccess && (
                        <span className="badge-in-group">
                          <Shield size={12} /> Has Access
                        </span>
                      )}
                    </div>
                    <div className="user-email">
                      {group.description || `${group.user_count} users`}
                    </div>
                  </div>
                  <div>
                    {!hasAccess && !agent.is_system && (
                      <button
                        onClick={() => onGrantToGroup(group.group_name, agent.name)}
                        className="btn-sm btn-primary"
                      >
                        <Plus size={14} />
                        Grant
                      </button>
                    )}
                    {hasAccess && !(agent.is_system && isSystemGroup) && (
                      <button
                        onClick={() => onRevokeFromGroup(group.group_name, agent.name)}
                        className="btn-sm btn-danger"
                      >
                        <Trash2 size={14} />
                        Revoke
                      </button>
                    )}
                    {agent.is_system && isSystemGroup && (
                      <span className="always-enabled-text">
                        Always enabled
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
              </div>
            </>
          )}
        </div>

        <div className="modal-actions">
          {!agent.is_system && (
            <div style={{ marginRight: 'auto' }}>
              {!showDeleteConfirm ? (
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  className="btn-danger"
                  style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
                >
                  <Trash2 size={16} />
                  Delete Agent
                </button>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ color: '#ef4444', fontWeight: '500' }}>
                    Are you sure?
                  </span>
                  <button
                    onClick={handleDelete}
                    className="btn-danger"
                    disabled={deleting}
                  >
                    {deleting ? 'Deleting...' : 'Yes, Delete'}
                  </button>
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    className="btn-secondary"
                    disabled={deleting}
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          )}
          <button onClick={onClose} className="btn-primary">
            Done
          </button>
        </div>
      </div>
    </div>
  )
}

export default ManageAgentAccessModal
