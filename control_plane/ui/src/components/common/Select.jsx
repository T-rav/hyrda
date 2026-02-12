import React, { forwardRef } from 'react'
import { ChevronDown } from 'lucide-react'

/**
 * Select component with Bootstrap-style classes
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
    'mb-4',
    className,
  ].filter(Boolean).join(' ')

  const selectClasses = [
    'form-select',
    hasError && 'is-invalid',
  ].filter(Boolean).join(' ')

  return (
    <div className={wrapperClasses}>
      {label && (
        <label htmlFor={selectId} className="form-label">
          {label}
          {required && <span className="text-danger ms-1">*</span>}
        </label>
      )}
      <div className="position-relative">
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

export default Select
