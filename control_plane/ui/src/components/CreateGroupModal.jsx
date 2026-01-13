import React, { useState } from 'react'
import { X } from 'lucide-react'

function CreateGroupModal({ onClose, onCreate }) {
  const [formData, setFormData] = useState({
    display_name: '',
    description: '',
    created_by: 'admin'
  })

  // Auto-generate group_name from display_name (slugify)
  const generateGroupName = (displayName) => {
    return displayName
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')  // Replace non-alphanumeric with underscore
      .replace(/^_+|_+$/g, '')       // Remove leading/trailing underscores
      .replace(/_+/g, '_')           // Replace multiple underscores with single
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const group_name = generateGroupName(formData.display_name)
    onCreate({ ...formData, group_name })
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Create New Group</h2>
          <button onClick={onClose} className="modal-close">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label>Group Name</label>
            <input
              type="text"
              value={formData.display_name}
              onChange={e => setFormData({ ...formData, display_name: e.target.value })}
              placeholder="Data Analysts"
              required
            />
          </div>

          <div className="form-group">
            <label>Description (optional)</label>
            <textarea
              value={formData.description}
              onChange={e => setFormData({ ...formData, description: e.target.value })}
              placeholder="Team members who analyze data"
              rows={3}
            />
          </div>

          <div className="modal-actions">
            <button type="button" onClick={onClose} className="btn-secondary">
              Cancel
            </button>
            <button type="submit" className="btn-primary">
              Create Group
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default CreateGroupModal
