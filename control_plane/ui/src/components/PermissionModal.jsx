import React, { useState } from 'react'
import { X, CheckCircle, Trash2 } from 'lucide-react'

function PermissionModal({ title, agents, onClose, onGrant, onRevoke }) {
  const [selectedAgent, setSelectedAgent] = useState('')

  const handleGrant = () => {
    if (selectedAgent) {
      onGrant(selectedAgent)
      setSelectedAgent('')
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button onClick={onClose} className="modal-close">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <div className="form-group">
            <label>Select Agent</label>
            <select
              value={selectedAgent}
              onChange={e => setSelectedAgent(e.target.value)}
              className="agent-select"
            >
              <option value="">-- Select an agent --</option>
              {agents.map(agent => (
                <option key={agent.name} value={agent.name}>
                  /{agent.name} - {agent.description}
                </option>
              ))}
            </select>
          </div>

          <div className="permission-actions">
            <button
              onClick={handleGrant}
              disabled={!selectedAgent}
              className="btn-primary"
            >
              <CheckCircle size={16} />
              Grant Access
            </button>
            <button
              onClick={() => selectedAgent && onRevoke(selectedAgent)}
              disabled={!selectedAgent}
              className="btn-danger"
            >
              <Trash2 size={16} />
              Revoke Access
            </button>
          </div>

          <div className="agent-list">
            <h4>Available Agents</h4>
            {agents.map(agent => (
              <div key={agent.name} className="agent-list-item">
                <strong>/{agent.name}</strong>
                <p>{agent.description}</p>
              </div>
            ))}
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
