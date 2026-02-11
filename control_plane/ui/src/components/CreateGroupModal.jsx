import React, { useState } from 'react'
import { Plus } from 'lucide-react'
import Modal from './common/Modal'
import Input from './common/Input'
import Textarea from './common/Textarea'
import Button from './common/Button'

/**
 * Modal for creating a new group
 *
 * @typedef {Object} CreateGroupModalProps
 * @property {Function} onClose - Callback when modal should close
 * @property {Function} onCreate - Callback when group is created
 */

function CreateGroupModal({ onClose, onCreate }) {
  const [formData, setFormData] = useState({
    display_name: '',
    description: '',
    created_by: 'admin'
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(null)

  // Auto-generate group_name from display_name (slugify)
  const generateGroupName = (displayName) => {
    return displayName
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')  // Replace non-alphanumeric with underscore
      .replace(/^_+|_+$/g, '')       // Remove leading/trailing underscores
      .replace(/_+/g, '_')           // Replace multiple underscores with single
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      const group_name = generateGroupName(formData.display_name)
      await onCreate({ ...formData, group_name })
      // Modal will be closed by parent on success
    } catch (err) {
      setError(err.message || 'Failed to create group')
      setIsSubmitting(false)
    }
  }

  const isFormValid = formData.display_name.trim().length > 0

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={
        <>
          <Plus size={20} className="me-2" />
          Create New Group
        </>
      }
      size="md"
    >
      <form onSubmit={handleSubmit}>
        <Input
          label="Group Name"
          value={formData.display_name}
          onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
          placeholder="Data Analysts"
          required
          autoFocus
          error={error}
        />

        <Textarea
          label="Description"
          value={formData.description}
          onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          placeholder="Team members who analyze data"
          rows={3}
          hint="Optional description to help identify this group"
        />

        <div className="modal-footer" style={{ margin: '0 -1.5rem -1.5rem' }}>
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            isLoading={isSubmitting}
            disabled={!isFormValid}
          >
            Create Group
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export default CreateGroupModal
