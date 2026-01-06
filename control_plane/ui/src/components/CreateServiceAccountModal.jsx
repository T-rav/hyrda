import React, { useState } from 'react'
import { X, Key, Copy, Check } from 'lucide-react'

/**
 * Modal for creating a new service account.
 * Shows API key ONCE after creation with copy functionality.
 */
function CreateServiceAccountModal({ onClose, onCreate, agents, createdApiKey, onAcknowledge }) {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    allowed_agents: [], // Empty = all agents
    rate_limit: 100,
    expires_at: '', // Optional ISO datetime
  })
  const [copied, setCopied] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()

    // Prepare data for API - hardcode scopes to agents:invoke
    const data = {
      ...formData,
      scopes: 'agents:invoke', // Always agents:invoke for now
      allowed_agents: formData.allowed_agents.length > 0 ? formData.allowed_agents : null,
      expires_at: formData.expires_at ? new Date(formData.expires_at).toISOString() : null,
    }

    await onCreate(data)
  }

  const handleCopyKey = () => {
    navigator.clipboard.writeText(createdApiKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
  }

  const handleAgentSelection = (e) => {
    const options = e.target.selectedOptions
    const selected = Array.from(options).map((opt) => opt.value)
    setFormData((prev) => ({ ...prev, allowed_agents: selected }))
  }

  // If API key was created, show the key display modal
  if (createdApiKey) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h2>
              <Key size={24} />
              Service Account Created!
            </h2>
            <button className="btn-icon" onClick={onClose}>
              <X size={20} />
            </button>
          </div>

          <div className="modal-body">
            <div className="alert alert-warning">
              <strong>⚠️ Save this API key now!</strong>
              <p>This is the only time it will be displayed. Store it securely.</p>
            </div>

            <div className="api-key-display">
              <label>API Key:</label>
              <div className="api-key-box">
                <code>{createdApiKey}</code>
                <button
                  className={`btn-secondary btn-sm ${copied ? 'btn-success' : ''}`}
                  onClick={handleCopyKey}
                  title="Copy to clipboard"
                >
                  {copied ? <Check size={16} /> : <Copy size={16} />}
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>

            <div className="alert alert-info">
              <p>
                <strong>How to use this API key:</strong>
              </p>
              <pre className="code-block">
{`# Option 1: X-API-Key header
curl -X POST http://agent-service:8000/api/agents/profile_researcher/invoke \\
  -H "X-API-Key: ${createdApiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "Research Tesla Inc", "context": {}}'

# Option 2: Authorization Bearer header
curl -X POST http://agent-service:8000/api/agents/profile_researcher/invoke \\
  -H "Authorization: Bearer ${createdApiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "Research Tesla Inc", "context": {}}'`}
              </pre>
            </div>
          </div>

          <div className="modal-footer">
            <button
              className="btn-primary"
              onClick={() => {
                onAcknowledge()
                onClose()
              }}
            >
              I've Saved the Key
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Otherwise, show the creation form
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>
            <Key size={24} />
            Create Service Account
          </h2>
          <button className="btn-icon" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {/* Name */}
            <div className="form-group">
              <label htmlFor="name">
                Name <span className="required">*</span>
              </label>
              <input
                type="text"
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                placeholder="e.g., HubSpot Production"
                required
                className="form-control"
              />
              <small>Unique identifier for this service account</small>
            </div>

            {/* Description */}
            <div className="form-group">
              <label htmlFor="description">Description</label>
              <textarea
                id="description"
                name="description"
                value={formData.description}
                onChange={handleChange}
                placeholder="Purpose and use case..."
                rows={3}
                className="form-control"
              />
            </div>

            {/* Allowed Agents */}
            <div className="form-group">
              <label>Allowed Agents</label>
              <div className="checkbox-grid">
                <label className="checkbox-card">
                  <input
                    type="checkbox"
                    checked={formData.allowed_agents.length === 0}
                    onChange={() => {
                      // Clicking "All Agents" always clears specific selections
                      setFormData((prev) => ({ ...prev, allowed_agents: [] }))
                    }}
                  />
                  <div className="checkbox-content">
                    <strong>All Agents</strong>
                    <small>Unrestricted access to all non-system agents</small>
                  </div>
                </label>
                {agents
                  .filter((agent) => !agent.is_system)
                  .map((agent) => (
                    <label key={agent.name} className="checkbox-card">
                      <input
                        type="checkbox"
                        checked={formData.allowed_agents.includes(agent.name)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            // Add this agent to the list
                            setFormData((prev) => ({
                              ...prev,
                              allowed_agents: [...prev.allowed_agents, agent.name],
                            }))
                          } else {
                            // Remove this agent from the list
                            const newList = formData.allowed_agents.filter((a) => a !== agent.name)
                            // If list becomes empty, it means "All Agents" by default
                            setFormData((prev) => ({
                              ...prev,
                              allowed_agents: newList,
                            }))
                          }
                        }}
                      />
                      <div className="checkbox-content">
                        <strong>{agent.display_name || agent.name}</strong>
                        {agent.description && <small>{agent.description}</small>}
                      </div>
                    </label>
                  ))}
              </div>
              <small>
                Select specific agents to restrict access, or leave "All Agents" checked for unrestricted access.
              </small>
            </div>

            {/* Rate Limit */}
            <div className="form-group">
              <label htmlFor="rate_limit">Rate Limit (requests/hour)</label>
              <input
                type="number"
                id="rate_limit"
                name="rate_limit"
                value={formData.rate_limit}
                onChange={handleChange}
                min={1}
                max={10000}
                className="form-control"
              />
            </div>

            {/* Expiration */}
            <div className="form-group">
              <label htmlFor="expires_at">Expiration Date (optional)</label>
              <input
                type="datetime-local"
                id="expires_at"
                name="expires_at"
                value={formData.expires_at}
                onChange={handleChange}
                className="form-control"
              />
              <small>Leave empty for no expiration</small>
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary">
              <Key size={16} />
              Create Service Account
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default CreateServiceAccountModal
