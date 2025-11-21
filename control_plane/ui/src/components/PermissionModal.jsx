import React, { useState } from 'react'
import { X, CheckCircle, Trash2, Shield } from 'lucide-react'

function PermissionModal({ title, agents, userPermissions = [], onClose, onGrant, onRevoke }) {
  const [searchTerm, setSearchTerm] = useState('')

  // Create set of agent names user already has access to
  const permittedAgentNames = new Set(userPermissions)

  const filteredAgents = agents.filter(agent =>
    agent.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    agent.description.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content large" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button onClick={onClose} className="modal-close">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <div className="form-group">
            <input
              type="text"
              placeholder="Search agents..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="search-input"
            />
          </div>

          <div className="user-selection-list">
            {filteredAgents.map(agent => {
              const hasAccess = permittedAgentNames.has(agent.name)

              return (
                <div key={agent.name} className="user-selection-item">
                  <div>
                    <div className="user-name">
                      /{agent.name}
                      {hasAccess && <span className="badge-in-group"><Shield size={12} /> Has Access</span>}
                    </div>
                    <div className="user-email">{agent.description}</div>
                  </div>
                  <div>
                    {!hasAccess && (
                      <button
                        onClick={() => onGrant(agent.name)}
                        className="btn-sm btn-primary"
                      >
                        <CheckCircle size={14} />
                        Grant
                      </button>
                    )}
                    {hasAccess && (
                      <button
                        onClick={() => onRevoke(agent.name)}
                        className="btn-sm btn-danger"
                      >
                        <Trash2 size={14} />
                        Revoke
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="modal-actions">
          <button onClick={onClose} className="btn-secondary">
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export default PermissionModal
