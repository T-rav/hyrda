import React, { useState } from 'react'
import { Users, X, Plus, Trash2, Shield } from 'lucide-react'

function ManageAgentAccessModal({ agent, groups, onClose, onGrantToGroup, onRevokeFromGroup, onToggle }) {
  const [searchTerm, setSearchTerm] = useState('')

  // Create set of authorized group names
  const authorizedGroupNames = new Set(agent.authorized_group_names || [])

  const filteredGroups = groups.filter(group =>
    (group.display_name || group.group_name).toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleToggle = () => {
    onToggle(agent.name)
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
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid #e2e8f0' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 600, color: '#1e293b' }}>Agent Status</h3>
              <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.75rem', color: '#64748b' }}>
                Control whether this agent is enabled or disabled
              </p>
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

          <div style={{ padding: '1rem', background: '#f8fafc', borderRadius: '0.5rem', border: '1px solid #e2e8f0', marginBottom: '1rem' }}>
            <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>
              💡 Grant or revoke access to groups. Users in these groups will automatically have access to this agent.
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
              const hasAccess = authorizedGroupNames.has(group.group_name)
              const isSystemGroup = group.group_name === 'all_users'

              return (
                <div key={group.group_name} className="user-selection-item">
                  <div>
                    <div className="user-name">{group.display_name || group.group_name}</div>
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem', flexWrap: 'wrap' }}>
                      {isSystemGroup && (
                        <span className="stat-badge" style={{
                          background: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)',
                          color: '#92400e',
                          border: '1px solid #fbbf24',
                          fontSize: '0.7rem'
                        }}>
                          System
                        </span>
                      )}
                      {hasAccess && (
                        <span className="badge-in-group">
                          <Shield size={12} /> Has Access
                        </span>
                      )}
                    </div>
                    <div className="user-email" style={{ marginTop: '0.25rem' }}>
                      {group.description || `${group.user_count} users`}
                    </div>
                  </div>
                  <div>
                    {!hasAccess && (
                      <button
                        onClick={() => onGrantToGroup(group.group_name, agent.name)}
                        className="btn-sm btn-primary"
                      >
                        <Plus size={14} />
                        Grant
                      </button>
                    )}
                    {hasAccess && (
                      <button
                        onClick={() => onRevokeFromGroup(group.group_name, agent.name)}
                        className="btn-sm btn-danger"
                      >
                        <Trash2 size={14} />
                        Revoke
                      </button>
                    )}
                  </div>
                </div>
              )
            })}</div>
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
