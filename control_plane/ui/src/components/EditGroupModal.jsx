import React, { useState } from 'react'
import { X } from 'lucide-react'

function EditGroupModal({ group, onClose, onUpdate }) {
  const [formData, setFormData] = useState({
    display_name: group.display_name || group.group_name,
    description: group.description || '',
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    onUpdate(group.group_name, formData)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Edit Group</h2>
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
            <button type="button" onClick={onClose} className="btn btn-outline-secondary">
              Cancel
            </button>
            <button type="submit" className="btn btn-outline-primary">
              Save Changes
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default EditGroupModal
