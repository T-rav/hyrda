import React, { forwardRef } from 'react'

/**
 * Input component with Bootstrap-style classes
 *
 * @typedef {Object} InputProps
 * @property {string} [type='text'] - Input type
 * @property {string} [value] - Input value
 * @property {Function} [onChange] - Change handler
 * @property {string} [placeholder] - Placeholder text
 * @property {string} [label] - Label text
 * @property {string} [error] - Error message
 * @property {string} [hint] - Help text
 * @property {boolean} [required=false] - Required field
 * @property {boolean} [disabled=false] - Disabled state
 * @property {React.ReactNode} [leftIcon] - Icon to display before input
 * @property {React.ReactNode} [rightIcon] - Icon to display after input
 * @property {string} [className] - Additional CSS classes
 * @property {string} [id] - Input id
 * @property {string} [name] - Input name
 * @property {boolean} [autoFocus=false] - Auto focus on mount
 */

const Input = forwardRef(function Input({
  type = 'text',
  value,
  onChange,
  placeholder,
  label,
  error,
  hint,
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
  const hasError = Boolean(error)
  const hasLeftIcon = Boolean(leftIcon)
  const hasRightIcon = Boolean(rightIcon)

  const wrapperClasses = [
    'mb-4',
    className,
  ].filter(Boolean).join(' ')

  const inputClasses = [
    'form-control',
    hasError && 'is-invalid',
    hasLeftIcon && 'ps-5',
    hasRightIcon && 'pe-5',
  ].filter(Boolean).join(' ')

  return (
    <div className={wrapperClasses}>
      {label && (
        <label htmlFor={inputId} className="form-label">
          {leftIcon && <span className="me-1">{leftIcon}</span>}
          {label}
          {required && <span className="text-danger ms-1">*</span>}
        </label>
      )}
      <div className="position-relative">
        {leftIcon && !label && (
          <span
            className="position-absolute"
            style={{
              left: '0.75rem',
              top: '50%',
              transform: 'translateY(-50%)',
              color: '#9ca3af',
              pointerEvents: 'none'
            }}
          >
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
          autoFocus={autoFocus}
          {...rest}
        />
        {rightIcon && (
          <span
            className="position-absolute"
            style={{
              right: '0.75rem',
              top: '50%',
              transform: 'translateY(-50%)',
              color: '#9ca3af',
              pointerEvents: 'none'
            }}
          >
            {rightIcon}
          </span>
        )}
      </div>
      {hint && !error && (
        <div id={hintId} className="form-text">
          {hint}
        </div>
      )}
      {error && (
        <div id={errorId} className="invalid-feedback" role="alert">
          {error}
        </div>
      )}
    </div>
  )
})

export default Input
