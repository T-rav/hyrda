import React from 'react'
import { Inbox } from 'lucide-react'
import Button from './Button'

/**
 * EmptyState component for when no data is available
 *
 * @typedef {Object} EmptyStateProps
 * @property {string} [title='No items found'] - Main heading
 * @property {string} [description] - Descriptive text
 * @property {React.ReactNode} [icon] - Custom icon component
 * @property {string} [actionLabel] - Primary action button text
 * @property {Function} [onAction] - Primary action handler
 * @property {string} [actionVariant='primary'] - Action button variant
 * @property {string} [className] - Additional CSS classes
 */

function EmptyState({
  title = 'No items found',
  description,
  icon,
  actionLabel,
  onAction,
  actionVariant = 'primary',
  className = '',
}) {
  const IconComponent = icon || <Inbox size={48} />

  return (
    <div className={`empty-state-container ${className}`.trim()}>
      <div className="empty-state-icon" aria-hidden="true">
        {IconComponent}
      </div>
      <h3 className="empty-state-title">{title}</h3>
      {description && (
        <p className="empty-state-description">{description}</p>
      )}
      {actionLabel && onAction && (
        <div className="empty-state-action">
          <Button variant={actionVariant} onClick={onAction}>
            {actionLabel}
          </Button>
        </div>
      )}
    </div>
  )
}

export default EmptyState
