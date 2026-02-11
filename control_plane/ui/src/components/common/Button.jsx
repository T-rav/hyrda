import React from 'react'
import { Loader2 } from 'lucide-react'

/**
 * Button component with consistent styling and accessibility
 *
 * @typedef {Object} ButtonProps
 * @property {React.ReactNode} children - Button content
 * @property {string} [variant='primary'] - Button style variant
 * @property {string} [size='md'] - Button size
 * @property {boolean} [isLoading=false] - Show loading spinner
 * @property {boolean} [disabled=false] - Disable button
 * @property {React.ReactNode} [leftIcon] - Icon to display before text
 * @property {React.ReactNode} [rightIcon] - Icon to display after text
 * @property {string} [type='button'] - Button type attribute
 * @property {Function} [onClick] - Click handler
 * @property {string} [className] - Additional CSS classes
 * @property {React.CSSProperties} [style] - Inline styles
 * @property {string} [title] - Tooltip text
 * @property {string} [ariaLabel] - Accessible label
 */

const VARIANTS = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  danger: 'btn-danger',
  success: 'btn-success',
  ghost: 'btn-ghost',
  link: 'btn-link',
}

const SIZES = {
  sm: 'btn-sm',
  md: '',
  lg: 'btn-lg',
}

function Button({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabled = false,
  leftIcon,
  rightIcon,
  type = 'button',
  onClick,
  className = '',
  style,
  title,
  ariaLabel,
  ...rest
}) {
  const baseClass = 'btn'
  const variantClass = VARIANTS[variant] || VARIANTS.primary
  const sizeClass = SIZES[size] || ''

  const classes = [
    baseClass,
    variantClass,
    sizeClass,
    isLoading && 'btn-loading',
    className,
  ].filter(Boolean).join(' ')

  const isDisabled = disabled || isLoading

  return (
    <button
      type={type}
      className={classes}
      style={style}
      onClick={onClick}
      disabled={isDisabled}
      title={title}
      aria-label={ariaLabel}
      aria-busy={isLoading}
      {...rest}
    >
      {isLoading && (
        <span className="btn-spinner" aria-hidden="true">
          <Loader2 size={size === 'sm' ? 14 : 16} />
        </span>
      )}
      {!isLoading && leftIcon && (
        <span className="btn-icon-left" aria-hidden="true">
          {leftIcon}
        </span>
      )}
      <span className={isLoading ? 'btn-text-loading' : ''}>
        {children}
      </span>
      {!isLoading && rightIcon && (
        <span className="btn-icon-right" aria-hidden="true">
          {rightIcon}
        </span>
      )}
    </button>
  )
}

export default Button
