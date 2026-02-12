import React, { useState, useEffect } from 'react'
import { X, CheckCircle, Trash2, Shield } from 'lucide-react'

function PermissionModal({ title, agents, userPermissions = [], onClose, onGrant, onRevoke }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [localPermissions, setLocalPermissions] = useState(new Set())

  // Sync local permissions with userPermissions prop
  useEffect(() => {
    setLocalPermissions(new Set(userPermissions))
  }, [userPermissions])

  const handleGrant = async (agentName) => {
    // Optimistically update UI
    setLocalPermissions(prev => new Set([...prev, agentName]))
    try {
      await onGrant(agentName)
    } catch (error) {
      // Revert on error
      setLocalPermissions(prev => {
        const next = new Set(prev)
        next.delete(agentName)
        return next
      })
    }
  }

  const handleRevoke = async (agentName) => {
    // Optimistically update UI
    setLocalPermissions(prev => {
      const next = new Set(prev)
      next.delete(agentName)
      return next
    })
    try {
      await onRevoke(agentName)
    } catch (error) {
      // Revert on error
      setLocalPermissions(prev => new Set([...prev, agentName]))
    }
  }

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
              const hasAccess = localPermissions.has(agent.name)

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
                        onClick={() => handleGrant(agent.name)}
                        className="btn-sm btn-outline-primary"
                      >
                        <CheckCircle size={14} />
                        Grant
                      </button>
                    )}
                    {hasAccess && (
                      <button
                        onClick={() => handleRevoke(agent.name)}
                        className="btn-sm btn-outline-danger"
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
          <button onClick={onClose} className="btn btn-outline-secondary">
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export default PermissionModal
