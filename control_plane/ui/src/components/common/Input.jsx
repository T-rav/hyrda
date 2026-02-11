import React, { forwardRef } from 'react'

/**
 * Input component with consistent styling and accessibility
 *
 * @typedef {Object} InputProps
 * @property {string} [type='text'] - Input type
 * @property {string} [value] - Input value
 * @property {Function} [onChange] - Change handler
 * @property {string} [placeholder] - Placeholder text
 * @property {string} [label] - Label text
 * @property {string} [error] - Error message
 * @property {string} [hint] - Help text
 * @property {string} [size='md'] - Input size (sm, md, lg)
 * @property {boolean} [required=false] - Required field
 * @property {boolean} [disabled=false] - Disabled state
 * @property {React.ReactNode} [leftIcon] - Icon to display before input
 * @property {React.ReactNode} [rightIcon] - Icon to display after input
 * @property {string} [className] - Additional CSS classes
 * @property {string} [id] - Input id
 * @property {string} [name] - Input name
 * @property {boolean} [autoFocus=false] - Auto focus on mount
 */

const SIZES = {
  sm: 'input-sm',
  md: '',
  lg: 'input-lg',
}

const Input = forwardRef(function Input({
  type = 'text',
  value,
  onChange,
  placeholder,
  label,
  error,
  hint,
  size = 'md',
  required = false,
  disabled = false,
  leftIcon,
  rightIcon,
  className = '',
  id,
  name,
  autoFocus = false,
  ...rest
}, ref) {
  const inputId = id || `input-${Math.random().toString(36).substr(2, 9)}`
  const errorId = error ? `${inputId}-error` : undefined
  const hintId = hint ? `${inputId}-hint` : undefined

  const ariaDescribedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined

  const sizeClass = SIZES[size] || ''
  const hasError = Boolean(error)
  const hasLeftIcon = Boolean(leftIcon)
  const hasRightIcon = Boolean(rightIcon)

  const wrapperClasses = [
    'input-wrapper',
    hasLeftIcon && 'input-has-left-icon',
    hasRightIcon && 'input-has-right-icon',
    className,
  ].filter(Boolean).join(' ')

  const inputClasses = [
    'input',
    sizeClass,
    hasError && 'input-error',
    hasLeftIcon && 'input-with-left-icon',
    hasRightIcon && 'input-with-right-icon',
  ].filter(Boolean).join(' ')

  return (
    <div className={wrapperClasses}>
      {label && (
        <label htmlFor={inputId} className="input-label">
          {label}
          {required && <span className="input-required" aria-hidden="true"> *</span>}
        </label>
      )}
      <div className="input-container">
        {leftIcon && (
          <span className="input-icon input-icon-left" aria-hidden="true">
            {leftIcon}
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          name={name}
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          disabled={disabled}
          required={required}
          className={inputClasses}
          aria-invalid={hasError}
          aria-describedby={ariaDescribedBy}
          aria-required={required}
          autoFocus={autoFocus}
          {...rest}
        />
        {rightIcon && (
          <span className="input-icon input-icon-right" aria-hidden="true">
            {rightIcon}
          </span>
        )}
      </div>
      {hint && !error && (
        <span id={hintId} className="input-hint">
          {hint}
        </span>
      )}
      {error && (
        <span id={errorId} className="input-error-message" role="alert">
          {error}
        </span>
      )}
    </div>
  )
})

export default Input
