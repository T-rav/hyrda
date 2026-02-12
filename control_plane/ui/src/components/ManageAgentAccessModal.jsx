import React, { useState, useEffect } from 'react'
import { Users, X, Plus, Trash2, Shield } from 'lucide-react'

function ManageAgentAccessModal({ agent, groups, onClose, onGrantToGroup, onRevokeFromGroup, onToggle }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [localAuthorizedGroups, setLocalAuthorizedGroups] = useState(new Set())

  // Sync local authorized groups with agent.authorized_group_names prop
  useEffect(() => {
    setLocalAuthorizedGroups(new Set(agent.authorized_group_names || []))
  }, [agent.authorized_group_names])

  const handleGrant = async (groupName, agentName) => {
    // Optimistically update UI
    setLocalAuthorizedGroups(prev => new Set([...prev, groupName]))
    try {
      await onGrantToGroup(groupName, agentName)
    } catch (error) {
      // Revert on error
      setLocalAuthorizedGroups(prev => {
        const next = new Set(prev)
        next.delete(groupName)
        return next
      })
    }
  }

  const handleRevoke = async (groupName, agentName) => {
    // Optimistically update UI
    setLocalAuthorizedGroups(prev => {
      const next = new Set(prev)
      next.delete(groupName)
      return next
    })
    try {
      await onRevokeFromGroup(groupName, agentName)
    } catch (error) {
      // Revert on error
      setLocalAuthorizedGroups(prev => new Set([...prev, groupName]))
    }
  }

  // For system agents, only show all_users group
  const filteredGroups = groups
    .filter(group => !agent.is_system || group.group_name === 'all_users')
    .filter(group =>
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
                <h3>Agent Status</h3>
                <p>
                  Disabled agents are hidden from the registry and <strong>cannot be invoked</strong> by
                  anyone (Slack, API, or service accounts). Use this to temporarily disable agents
                  without deleting them.
                </p>
              </div>
              <div className="toggle-switch" onClick={handleToggle}>
                <input
                  type="checkbox"
                  checked={agent.is_enabled}
                  onChange={() => {}}
                  className="toggle-checkbox"
                />
                <span className="toggle-slider"></span>
                <span className="toggle-label">
                  {agent.is_enabled ? 'Enabled' : 'Disabled'}
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
              const hasAccess = localAuthorizedGroups.has(group.group_name)
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
                        onClick={() => handleGrant(group.group_name, agent.name)}
                        className="btn btn-sm btn-outline-primary"
                      >
                        <Plus size={14} />
                        Grant
                      </button>
                    )}
                    {hasAccess && !(agent.is_system && isSystemGroup) && (
                      <button
                        onClick={() => handleRevoke(group.group_name, agent.name)}
                        className="btn btn-sm btn-outline-danger"
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
          <button onClick={onClose} className="btn btn-outline-secondary">
            Done
          </button>
        </div>
      </div>
    </div>
  )
}

export default ManageAgentAccessModal
