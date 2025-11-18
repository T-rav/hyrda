import React, { useState } from 'react'
import { X } from 'lucide-react'

function CreateGroupModal({ onClose, onCreate }) {
  const [formData, setFormData] = useState({
    group_name: '',
    display_name: '',
    description: '',
    created_by: 'admin'
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    onCreate(formData)
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
            <label>Group ID (lowercase, no spaces)</label>
            <input
              type="text"
              value={formData.group_name}
              onChange={e => setFormData({ ...formData, group_name: e.target.value })}
              placeholder="analysts"
              pattern="[a-z_]+"
              required
            />
          </div>

          <div className="form-group">
            <label>Display Name</label>
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
