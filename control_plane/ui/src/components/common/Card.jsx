import React from 'react'

/**
 * Card component for consistent container styling
 *
 * @typedef {Object} CardProps
 * @property {React.ReactNode} children - Card content
 * @property {string} [variant='default'] - Card variant (default, outlined, ghost)
 * @property {boolean} [hoverable=false] - Add hover effect
 * @property {boolean} [clickable=false] - Add cursor pointer
 * @property {Function} [onClick] - Click handler
 * @property {string} [className] - Additional CSS classes
 * @property {React.ReactNode} [header] - Card header content
 * @property {React.ReactNode} [footer] - Card footer content
 * @property {string} [title] - Card title (renders in header)
 */

const VARIANTS = {
  default: 'card',
  outlined: 'card card-outlined',
  ghost: 'card card-ghost',
}

function Card({
  children,
  variant = 'default',
  hoverable = false,
  clickable = false,
  onClick,
  className = '',
  header,
  footer,
  title,
}) {
  const baseClass = VARIANTS[variant] || VARIANTS.default

  const classes = [
    baseClass,
    hoverable && 'card-hoverable',
    (clickable || onClick) && 'card-clickable',
    className,
  ].filter(Boolean).join(' ')

  const hasHeader = header || title

  return (
    <div
      className={classes}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {hasHeader && (
        <div className="card-header">
          {title && <h3 className="card-title">{title}</h3>}
          {header}
        </div>
      )}
      <div className="card-body">
        {children}
      </div>
      {footer && (
        <div className="card-footer">
          {footer}
        </div>
      )}
    </div>
  )
}

export default Card
