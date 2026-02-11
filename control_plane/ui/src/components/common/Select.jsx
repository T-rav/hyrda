import React, { forwardRef } from 'react'
import { ChevronDown } from 'lucide-react'

/**
 * Select component with consistent styling and accessibility
 *
 * @typedef {Object} SelectOption
 * @property {string} value - Option value
 * @property {string} label - Option label
 * @property {boolean} [disabled] - Option disabled state
 *
 * @typedef {Object} SelectProps
 * @property {string} [value] - Selected value
 * @property {Function} [onChange] - Change handler
 * @property {SelectOption[]} options - Select options
 * @property {string} [placeholder] - Placeholder text (shown as first disabled option)
 * @property {string} [label] - Label text
 * @property {string} [error] - Error message
 * @property {string} [hint] - Help text
 * @property {boolean} [required=false] - Required field
 * @property {boolean} [disabled=false] - Disabled state
 * @property {string} [className] - Additional CSS classes
 * @property {string} [id] - Select id
 * @property {string} [name] - Select name
 */

const Select = forwardRef(function Select({
  value,
  onChange,
  options = [],
  placeholder,
  label,
  error,
  hint,
  required = false,
  disabled = false,
  className = '',
  id,
  name,
  ...rest
}, ref) {
  const selectId = id || `select-${Math.random().toString(36).substr(2, 9)}`
  const errorId = error ? `${selectId}-error` : undefined
  const hintId = hint ? `${selectId}-hint` : undefined

  const ariaDescribedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined
  const hasError = Boolean(error)

  const wrapperClasses = [
    'input-wrapper',
    'select-wrapper',
    className,
  ].filter(Boolean).join(' ')

  const selectClasses = [
    'input',
    'select',
    hasError && 'input-error',
  ].filter(Boolean).join(' ')

  return (
    <div className={wrapperClasses}>
      {label && (
        <label htmlFor={selectId} className="input-label">
          {label}
          {required && <span className="input-required" aria-hidden="true"> *</span>}
        </label>
      )}
      <div className="select-container">
        <select
          ref={ref}
          id={selectId}
          name={name}
          value={value}
          onChange={onChange}
          disabled={disabled}
          required={required}
          className={selectClasses}
          aria-invalid={hasError}
          aria-describedby={ariaDescribedBy}
          aria-required={required}
          {...rest}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((option) => (
            <option
              key={option.value}
              value={option.value}
              disabled={option.disabled}
            >
              {option.label}
            </option>
          ))}
        </select>
        <span className="select-icon" aria-hidden="true">
          <ChevronDown size={16} />
        </span>
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

export default Select
