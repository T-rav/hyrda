import React from 'react'

/**
 * ToggleSwitch Component
 *
 * A visual toggle switch for boolean values.
 * Supports both editable and read-only modes.
 *
 * @param {string} id - Unique identifier for the input
 * @param {boolean} checked - Current state of the toggle
 * @param {function} onChange - Callback when toggle changes (checked) => void
 * @param {boolean} disabled - Whether the toggle is disabled/read-only
 * @param {string} labelOn - Label to show when checked (default: "Yes")
 * @param {string} labelOff - Label to show when unchecked (default: "No")
 * @param {string} label - Optional label to display above the toggle
 * @param {string} helpText - Optional help text to display below the toggle
 */
function ToggleSwitch({
  id,
  checked,
  onChange,
  disabled = false,
  labelOn = 'Yes',
  labelOff = 'No',
  label,
  helpText,
}) {
  const handleChange = (e) => {
    if (!disabled && onChange) {
      onChange(e.target.checked)
    }
  }

  return (
    <div className="toggle-switch-wrapper">
      {label && (
        <label htmlFor={id} className="form-label">
          {label}
        </label>
      )}
      <div className="toggle-switch-container">
        <label className={`toggle-switch ${disabled ? 'disabled' : ''}`}>
          <input
            type="checkbox"
            id={id}
            checked={checked}
            onChange={handleChange}
            disabled={disabled}
            aria-checked={checked}
          />
          <span className="toggle-slider">
            <span className="toggle-knob"></span>
          </span>
        </label>
        <span className={`toggle-label ${checked ? 'active' : ''}`}>
          {checked ? labelOn : labelOff}
        </span>
      </div>
      {helpText && (
        <div className="form-text">
          <small className="text-muted">{helpText}</small>
        </div>
      )}
    </div>
  )
}

export default ToggleSwitch
