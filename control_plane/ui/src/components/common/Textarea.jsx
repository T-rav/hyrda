import React, { forwardRef } from 'react'

/**
 * Textarea component with consistent styling and accessibility
 *
 * @typedef {Object} TextareaProps
 * @property {string} [value] - Textarea value
 * @property {Function} [onChange] - Change handler
 * @property {string} [placeholder] - Placeholder text
 * @property {string} [label] - Label text
 * @property {string} [error] - Error message
 * @property {string} [hint] - Help text
 * @property {number} [rows=3] - Number of rows
 * @property {boolean} [required=false] - Required field
 * @property {boolean} [disabled=false] - Disabled state
 * @property {boolean} [resize=true] - Allow resizing
 * @property {string} [className] - Additional CSS classes
 * @property {string} [id] - Textarea id
 * @property {string} [name] - Textarea name
 * @property {boolean} [autoFocus=false] - Auto focus on mount
 */

const Textarea = forwardRef(function Textarea({
  value,
  onChange,
  placeholder,
  label,
  error,
  hint,
  rows = 3,
  required = false,
  disabled = false,
  resize = true,
  className = '',
  id,
  name,
  autoFocus = false,
  ...rest
}, ref) {
  const textareaId = id || `textarea-${Math.random().toString(36).substr(2, 9)}`
  const errorId = error ? `${textareaId}-error` : undefined
  const hintId = hint ? `${textareaId}-hint` : undefined

  const ariaDescribedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined
  const hasError = Boolean(error)

  const wrapperClasses = [
    'input-wrapper',
    className,
  ].filter(Boolean).join(' ')

  const textareaClasses = [
    'input',
    'textarea',
    hasError && 'input-error',
    !resize && 'textarea-no-resize',
  ].filter(Boolean).join(' ')

  return (
    <div className={wrapperClasses}>
      {label && (
        <label htmlFor={textareaId} className="input-label">
          {label}
          {required && <span className="input-required" aria-hidden="true"> *</span>}
        </label>
      )}
      <textarea
        ref={ref}
        id={textareaId}
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        rows={rows}
        disabled={disabled}
        required={required}
        className={textareaClasses}
        aria-invalid={hasError}
        aria-describedby={ariaDescribedBy}
        aria-required={required}
        autoFocus={autoFocus}
        {...rest}
      />
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

export default Textarea
