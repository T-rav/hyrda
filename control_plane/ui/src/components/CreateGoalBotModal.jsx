import React, { useState, useEffect } from 'react'
import { X, Target } from 'lucide-react'

function CreateGoalBotModal({ isOpen, onClose, onCreate, onUpdate, editingBot, agents }) {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    agent_name: '',
    goal_prompt: '',
    schedule_type: 'interval',
    cron_expression: '0 0 * * *',
    interval_hours: 1,
    max_runtime_seconds: 3600,
    max_iterations: 10,
    notification_channel: '',
    tools: [],
  })
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  // Populate form when editing
  useEffect(() => {
    if (editingBot) {
      const intervalSeconds = editingBot.schedule_config?.interval_seconds || 3600
      setFormData({
        name: editingBot.name || '',
        description: editingBot.description || '',
        agent_name: editingBot.agent_name || '',
        goal_prompt: editingBot.goal_prompt || '',
        schedule_type: editingBot.schedule_type || 'interval',
        cron_expression: editingBot.schedule_config?.cron_expression || '0 0 * * *',
        interval_hours: intervalSeconds / 3600,
        max_runtime_seconds: editingBot.max_runtime_seconds || 3600,
        max_iterations: editingBot.max_iterations || 10,
        notification_channel: editingBot.notification_channel || '',
        tools: editingBot.tools || [],
      })
    }
  }, [editingBot])

  const validateForm = () => {
    const newErrors = {}

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required'
    }
    if (!formData.agent_name) {
      newErrors.agent_name = 'Agent is required'
    }
    if (!formData.goal_prompt.trim()) {
      newErrors.goal_prompt = 'Goal prompt is required'
    }
    if (formData.schedule_type === 'cron' && !formData.cron_expression.trim()) {
      newErrors.cron_expression = 'Cron expression is required'
    }
    if (formData.schedule_type === 'interval' && formData.interval_hours <= 0) {
      newErrors.interval_hours = 'Interval must be positive'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!validateForm()) return

    setSubmitting(true)
    try {
      const payload = {
        name: formData.name.trim(),
        description: formData.description.trim() || null,
        agent_name: formData.agent_name,
        goal_prompt: formData.goal_prompt.trim(),
        schedule_type: formData.schedule_type,
        schedule_config: formData.schedule_type === 'cron'
          ? { cron_expression: formData.cron_expression.trim() }
          : { interval_seconds: Math.round(formData.interval_hours * 3600) },
        max_runtime_seconds: formData.max_runtime_seconds,
        max_iterations: formData.max_iterations,
        notification_channel: formData.notification_channel.trim() || null,
        tools: formData.tools.length > 0 ? formData.tools : null,
      }

      if (editingBot) {
        await onUpdate(editingBot.bot_id, payload)
      } else {
        await onCreate(payload)
      }

      onClose()
    } catch (err) {
      console.error('Submit error:', err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: null }))
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <Target size={24} />
            <h2>{editingBot ? 'Edit Goal' : 'Create Goal'}</h2>
          </div>
          <button className="close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-group">
              <label htmlFor="name">Name *</label>
              <input
                id="name"
                type="text"
                value={formData.name}
                onChange={e => handleChange('name', e.target.value)}
                placeholder="e.g., Daily Report Generator"
                className={errors.name ? 'error' : ''}
              />
              {errors.name && <span className="error-text">{errors.name}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="description">Description</label>
              <input
                id="description"
                type="text"
                value={formData.description}
                onChange={e => handleChange('description', e.target.value)}
                placeholder="Brief description of what this bot does"
              />
            </div>

            <div className="form-group">
              <label htmlFor="agent_name">Agent *</label>
              <select
                id="agent_name"
                value={formData.agent_name}
                onChange={e => handleChange('agent_name', e.target.value)}
                className={errors.agent_name ? 'error' : ''}
              >
                <option value="">Select an agent...</option>
                {agents.filter(a => a.is_enabled).map(agent => (
                  <option key={agent.name} value={agent.name}>
                    {agent.display_name || agent.name}
                  </option>
                ))}
              </select>
              {errors.agent_name && <span className="error-text">{errors.agent_name}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="goal_prompt">Goal Prompt *</label>
              <textarea
                id="goal_prompt"
                value={formData.goal_prompt}
                onChange={e => handleChange('goal_prompt', e.target.value)}
                placeholder="Describe the goal this bot should achieve..."
                rows={4}
                className={errors.goal_prompt ? 'error' : ''}
              />
              {errors.goal_prompt && <span className="error-text">{errors.goal_prompt}</span>}
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="schedule_type">Schedule Type</label>
                <select
                  id="schedule_type"
                  value={formData.schedule_type}
                  onChange={e => handleChange('schedule_type', e.target.value)}
                >
                  <option value="interval">Interval</option>
                  <option value="cron">Cron</option>
                </select>
              </div>

              {formData.schedule_type === 'cron' ? (
                <div className="form-group">
                  <label htmlFor="cron_expression">Cron Expression *</label>
                  <input
                    id="cron_expression"
                    type="text"
                    value={formData.cron_expression}
                    onChange={e => handleChange('cron_expression', e.target.value)}
                    placeholder="0 0 * * *"
                    className={errors.cron_expression ? 'error' : ''}
                  />
                  {errors.cron_expression && <span className="error-text">{errors.cron_expression}</span>}
                  <span className="help-text">e.g., "0 9 * * *" = daily at 9am</span>
                </div>
              ) : (
                <div className="form-group">
                  <label htmlFor="interval_hours">Interval (hours) *</label>
                  <input
                    id="interval_hours"
                    type="number"
                    min="0.1"
                    step="0.1"
                    value={formData.interval_hours}
                    onChange={e => handleChange('interval_hours', parseFloat(e.target.value))}
                    className={errors.interval_hours ? 'error' : ''}
                  />
                  {errors.interval_hours && <span className="error-text">{errors.interval_hours}</span>}
                </div>
              )}
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="max_runtime_seconds">Max Runtime (seconds)</label>
                <input
                  id="max_runtime_seconds"
                  type="number"
                  min="60"
                  max="86400"
                  value={formData.max_runtime_seconds}
                  onChange={e => handleChange('max_runtime_seconds', parseInt(e.target.value))}
                />
                <span className="help-text">1 min - 24 hours</span>
              </div>

              <div className="form-group">
                <label htmlFor="max_iterations">Max Iterations</label>
                <input
                  id="max_iterations"
                  type="number"
                  min="1"
                  max="100"
                  value={formData.max_iterations}
                  onChange={e => handleChange('max_iterations', parseInt(e.target.value))}
                />
                <span className="help-text">Plan-execute-check cycles</span>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="notification_channel">Notification Channel</label>
              <input
                id="notification_channel"
                type="text"
                value={formData.notification_channel}
                onChange={e => handleChange('notification_channel', e.target.value)}
                placeholder="#channel-name"
              />
              <span className="help-text">Slack channel for run notifications</span>
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : (editingBot ? 'Update' : 'Create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default CreateGoalBotModal
