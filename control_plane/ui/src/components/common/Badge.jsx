import React from 'react'

/**
 * Badge component for status indicators and labels
 *
 * @typedef {Object} BadgeProps
 * @property {React.ReactNode} children - Badge content
 * @property {string} [variant='default'] - Badge color variant
 * @property {string} [size='md'] - Badge size (sm, md, lg)
 * @property {React.ReactNode} [leftIcon] - Icon before text
 * @property {React.ReactNode} [rightIcon] - Icon after text
 * @property {string} [className] - Additional CSS classes
 */

const VARIANTS = {
  default: 'badge',
  primary: 'badge badge-primary',
  secondary: 'badge badge-secondary',
  success: 'badge badge-success',
  danger: 'badge badge-danger',
  warning: 'badge badge-warning',
  info: 'badge badge-info',
  outline: 'badge badge-outline',
}

const SIZES = {
  sm: 'badge-sm',
  md: '',
  lg: 'badge-lg',
}

function Badge({
  children,
  variant = 'default',
  size = 'md',
  leftIcon,
  rightIcon,
  className = '',
}) {
  const variantClass = VARIANTS[variant] || VARIANTS.default
  const sizeClass = SIZES[size] || ''

  const classes = [
    variantClass,
    sizeClass,
    className,
  ].filter(Boolean).join(' ')

  return (
    <span className={classes}>
      {leftIcon && (
        <span className="badge-icon badge-icon-left" aria-hidden="true">
          {leftIcon}
        </span>
      )}
      <span className="badge-text">{children}</span>
      {rightIcon && (
        <span className="badge-icon badge-icon-right" aria-hidden="true">
          {rightIcon}
        </span>
      )}
    </span>
  )
}

export default Badge
