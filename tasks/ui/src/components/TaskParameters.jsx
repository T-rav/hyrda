import React, { useState, useEffect } from 'react'
import { Activity } from 'lucide-react'
import ToggleSwitch from './ToggleSwitch'
import { logError } from '../utils/logger'

/**
 * TaskParameters Component
 *
 * Renders parameter inputs for task creation/editing or viewing.
 * Supports editable mode (for create/edit) and read-only mode (for viewing).
 *
 * @param {string} taskType - The selected task type
 * @param {Array} taskTypes - Array of available task types with their metadata
 * @param {Object} values - Current parameter values (for controlled components)
 * @param {boolean} readOnly - Whether to render in read-only mode
 * @param {function} onChange - Callback when any parameter changes (param, value) => void
 */
function TaskParameters({
  taskType,
  taskTypes,
  values = {},
  readOnly = false,
  onChange
}) {
  const [selectedCredential, setSelectedCredential] = useState('')
  const [availableCredentials, setAvailableCredentials] = useState([])

  const selectedTaskType = taskTypes.find(tt => tt.type === taskType)

  // Special handling for jobs that require credentials
  const isGDriveIngest = taskType === 'gdrive_ingest'
  const isHubSpotSync = taskType === 'hubspot_sync'
  const needsGoogleCredentials = isGDriveIngest
  const needsHubSpotCredentials = isHubSpotSync
  const needsCredentials = needsGoogleCredentials || needsHubSpotCredentials

  // Load available credentials for jobs that need authentication
  useEffect(() => {
    if (needsCredentials && !readOnly) {
      fetch('/api/credentials', { credentials: 'include' })
        .then(r => r.json())
        .then(data => {
          // Filter credentials by provider type
          let filteredCreds = data.credentials || []
          if (needsHubSpotCredentials) {
            filteredCreds = filteredCreds.filter(c => c.provider === 'hubspot')
          } else if (needsGoogleCredentials) {
            // Google credentials use 'google_drive' or 'google' as provider
            filteredCreds = filteredCreds.filter(c =>
              c.provider === 'google_drive' || c.provider === 'google'
            )
          }
          setAvailableCredentials(filteredCreds)
          if (filteredCreds.length === 1) {
            setSelectedCredential(filteredCreds[0].credential_id)
            // Auto-set the credential_id param
            if (onChange) {
              onChange('credential_id', filteredCreds[0].credential_id)
            }
          }
        })
        .catch(err => {
          logError('Error loading credentials:', err)
        })
    }
  }, [needsCredentials, needsHubSpotCredentials, needsGoogleCredentials, readOnly])

  // Initialize selected credential from values in read-only mode
  useEffect(() => {
    if (readOnly && values.credential_id) {
      setSelectedCredential(values.credential_id)
    }
  }, [readOnly, values.credential_id])

  const handleParamChange = (param, value) => {
    if (onChange) {
      onChange(param, value)
    }
  }

  if (!selectedTaskType) {
    return (
      <div className="alert alert-info">
        <Activity size={16} className="me-2" />
        <small>Parameters will appear here based on the selected task type</small>
      </div>
    )
  }

  /**
   * Render a boolean parameter as a toggle switch
   */
  const renderBooleanParam = (param, isRequired, label, helpText, defaultValue = false) => {
    const currentValue = values[param] !== undefined ? values[param] : defaultValue

    if (readOnly) {
      return (
        <div className="mb-3">
          <ToggleSwitch
            id={`param_${param}`}
            checked={currentValue}
            disabled={true}
            label={label}
            helpText={helpText}
          />
        </div>
      )
    }

    return (
      <div className="mb-3">
        <ToggleSwitch
          id={`param_${param}`}
          checked={currentValue}
          onChange={(checked) => handleParamChange(param, checked)}
          label={label}
          helpText={helpText}
        />
      </div>
    )
  }

  /**
   * Render a text input parameter
   */
  const renderTextParam = (param, isRequired, label, placeholder, helpText) => {
    const currentValue = values[param] || ''

    return (
      <div className="mb-3">
        <label htmlFor={`param_${param}`} className="form-label">
          {label} {isRequired && <span className="text-danger">*</span>}
        </label>
        <input
          type="text"
          className="form-control"
          id={`param_${param}`}
          placeholder={placeholder}
          required={isRequired}
          disabled={readOnly}
          value={currentValue}
          onChange={(e) => handleParamChange(param, e.target.value)}
        />
        {helpText && (
          <div className="form-text">
            <small className="text-muted">{helpText}</small>
          </div>
        )}
      </div>
    )
  }

  /**
   * Render a select dropdown parameter
   */
  const renderSelectParam = (param, isRequired, label, options, helpText, defaultValue = '') => {
    const currentValue = values[param] !== undefined ? String(values[param]) : defaultValue

    if (readOnly) {
      // In read-only mode, show the selected option label
      const selectedOption = options.find(opt => opt.value === currentValue)
      return (
        <div className="mb-3">
          <label className="form-label">{label}</label>
          <div className="form-control" style={{ backgroundColor: '#f8f9fa' }}>
            {selectedOption ? selectedOption.label : currentValue}
          </div>
          {helpText && (
            <div className="form-text">
              <small className="text-muted">{helpText}</small>
            </div>
          )}
        </div>
      )
    }

    return (
      <div className="mb-3">
        <label htmlFor={`param_${param}`} className="form-label">
          {label} {isRequired && <span className="text-danger">*</span>}
        </label>
        <select
          className="form-select"
          id={`param_${param}`}
          required={isRequired}
          value={currentValue}
          onChange={(e) => {
            const value = e.target.value
            // Convert boolean strings to actual booleans
            if (value === 'true') {
              handleParamChange(param, true)
            } else if (value === 'false') {
              handleParamChange(param, false)
            } else {
              handleParamChange(param, value)
            }
          }}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {helpText && (
          <div className="form-text">
            <small className="text-muted">{helpText}</small>
          </div>
        )}
      </div>
    )
  }

  /**
   * Render a number input parameter
   */
  const renderNumberParam = (param, isRequired, label, placeholder, helpText, min, max, defaultValue) => {
    const currentValue = values[param] !== undefined ? values[param] : (defaultValue || '')

    return (
      <div className="mb-3">
        <label htmlFor={`param_${param}`} className="form-label">
          {label} {isRequired && <span className="text-danger">*</span>}
        </label>
        <input
          type="number"
          className="form-control"
          id={`param_${param}`}
          placeholder={placeholder}
          min={min}
          max={max}
          required={isRequired}
          disabled={readOnly}
          value={currentValue}
          onChange={(e) => handleParamChange(param, e.target.value ? parseInt(e.target.value) : '')}
        />
        {helpText && (
          <div className="form-text">
            <small className="text-muted">{helpText}</small>
          </div>
        )}
      </div>
    )
  }

  /**
   * Render a textarea parameter (e.g., for metadata JSON)
   */
  const renderTextareaParam = (param, isRequired, label, placeholder, helpText, rows = 3) => {
    const currentValue = values[param] !== undefined
      ? (typeof values[param] === 'object' ? JSON.stringify(values[param], null, 2) : values[param])
      : ''

    if (readOnly && typeof values[param] === 'object') {
      // In read-only mode, show object values as formatted JSON
      return (
        <div className="mb-3">
          <label className="form-label">{label}</label>
          <pre className="form-control" style={{ backgroundColor: '#f8f9fa', fontSize: '0.875rem' }}>
            <code>{currentValue}</code>
          </pre>
          {helpText && (
            <div className="form-text">
              <small className="text-muted">{helpText}</small>
            </div>
          )}
        </div>
      )
    }

    return (
      <div className="mb-3">
        <label htmlFor={`param_${param}`} className="form-label">
          {label} {isRequired && <span className="text-danger">*</span>}
        </label>
        <textarea
          className="form-control"
          id={`param_${param}`}
          rows={rows}
          placeholder={placeholder}
          required={isRequired}
          disabled={readOnly}
          value={currentValue}
          onChange={(e) => {
            const value = e.target.value
            if (param === 'metadata' && value.trim()) {
              try {
                handleParamChange(param, JSON.parse(value.trim()))
              } catch {
                // If not valid JSON, store as string for now
                handleParamChange(param, value.trim())
              }
            } else {
              handleParamChange(param, value)
            }
          }}
        />
        {helpText && (
          <div className="form-text">
            <small className="text-muted">{helpText}</small>
          </div>
        )}
      </div>
    )
  }

  /**
   * Render a multi-select parameter
   */
  const renderMultiSelectParam = (param, isRequired, label, options, helpText) => {
    const currentValue = values[param] || []
    const selectedValues = Array.isArray(currentValue) ? currentValue : [currentValue]

    if (readOnly) {
      // In read-only mode, show selected labels
      const selectedLabels = selectedValues.map(val => {
        const option = options.find(opt => opt.value === val)
        return option ? option.label : val
      })

      return (
        <div className="mb-3">
          <label className="form-label">{label}</label>
          <div className="form-control" style={{ backgroundColor: '#f8f9fa' }}>
            {selectedLabels.length > 0 ? selectedLabels.join(', ') : 'None selected'}
          </div>
          {helpText && (
            <div className="form-text">
              <small className="text-muted">{helpText}</small>
            </div>
          )}
        </div>
      )
    }

    return (
      <div className="mb-3">
        <label htmlFor={`param_${param}`} className="form-label">
          {label} {isRequired && <span className="text-danger">*</span>}
        </label>
        <select
          className="form-select"
          id={`param_${param}`}
          multiple
          required={isRequired}
          value={selectedValues}
          onChange={(e) => {
            const selectedOptions = Array.from(e.target.selectedOptions).map(option => option.value)
            handleParamChange(param, selectedOptions)
          }}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {helpText && (
          <div className="form-text">
            <small className="text-muted">{helpText}</small>
          </div>
        )}
      </div>
    )
  }

  const renderParameter = (param, isRequired = false) => {
    // Skip credentials_file, token_file, and credential_id for jobs that use credential selector (handled separately)
    if ((needsGoogleCredentials || needsHubSpotCredentials) && (param === 'credentials_file' || param === 'token_file' || param === 'credential_id')) {
      return null
    }

    // Specific parameter handling for known parameters
    switch (param) {
      case 'workspace_filter':
        return renderTextParam(
          param,
          isRequired,
          'Workspace Filter',
          'e.g., my-workspace-id',
          'Filter users by specific workspace ID (leave empty for all workspaces)'
        )

      case 'user_types':
        return renderMultiSelectParam(
          param,
          isRequired,
          'User Types',
          [
            { value: 'member', label: 'Member' },
            { value: 'admin', label: 'Admin' },
            { value: 'owner', label: 'Owner' },
            { value: 'bot', label: 'Bot' },
          ],
          'Select which types of users to import'
        )

      case 'include_deactivated':
        return renderBooleanParam(
          param,
          isRequired,
          'Include Deactivated Users',
          'Whether to include deactivated/deleted users in the import',
          false
        )

      case 'folder_id':
        return renderTextParam(
          param,
          false, // Not strictly required (can use file_id instead)
          'Folder ID',
          'Google Drive folder ID',
          'Provide either folder_id OR file_id (not both). Folder ID for ingesting a folder of documents.'
        )

      case 'file_id':
        return renderTextParam(
          param,
          false, // Not strictly required (can use folder_id instead)
          'File ID',
          'Google Drive file ID',
          'Provide either folder_id OR file_id (not both). File ID for ingesting a single document.'
        )

      case 'recursive':
        return renderBooleanParam(
          param,
          isRequired,
          'Include Subfolders',
          'Whether to recursively ingest documents from subfolders (only applies to folder_id)',
          true
        )

      case 'file_types':
        return renderTextParam(
          param,
          isRequired,
          'File Types',
          'pdf,docx,txt',
          'Comma-separated list of file types to process (e.g., pdf,docx,txt)'
        )

      case 'force_update':
        return renderBooleanParam(
          param,
          isRequired,
          'Force Update',
          'Whether to reprocess files that have already been ingested',
          false
        )

      case 'metadata':
        return renderTextareaParam(
          param,
          isRequired,
          'Metadata',
          '{"project": "my-project", "department": "engineering"}',
          'Additional metadata as JSON object (optional)'
        )

      case 'metric_types':
        return renderMultiSelectParam(
          param,
          isRequired,
          'Metric Types',
          [
            { value: 'system', label: 'System Metrics' },
            { value: 'usage', label: 'Usage Metrics' },
            { value: 'performance', label: 'Performance Metrics' },
            { value: 'errors', label: 'Error Metrics' },
          ],
          'Select which types of metrics to collect'
        )

      case 'time_range_hours':
        return renderNumberParam(
          param,
          isRequired,
          'Time Range (Hours)',
          '24',
          'Number of hours to collect metrics for (1-168 hours)',
          1,
          168,
          24
        )

      case 'aggregate_level':
        return renderSelectParam(
          param,
          isRequired,
          'Aggregate Level',
          [
            { value: 'hourly', label: 'Hourly' },
            { value: 'daily', label: 'Daily' },
            { value: 'weekly', label: 'Weekly' },
          ],
          'Level of aggregation for collected metrics',
          'hourly'
        )

      // YouTube-specific parameters
      case 'channel_url':
        return renderTextParam(
          param,
          isRequired,
          'Channel URL',
          'https://www.youtube.com/@ChannelName',
          'YouTube channel URL to ingest videos from'
        )

      case 'include_videos':
        return renderBooleanParam(
          param,
          isRequired,
          'Include Videos',
          'Include regular videos in the ingestion',
          true
        )

      case 'include_shorts':
        return renderBooleanParam(
          param,
          isRequired,
          'Include Shorts',
          'Include YouTube Shorts in the ingestion',
          false
        )

      case 'include_podcasts':
        return renderBooleanParam(
          param,
          isRequired,
          'Include Podcasts',
          'Include podcast episodes in the ingestion',
          false
        )

      case 'max_videos':
        return renderNumberParam(
          param,
          isRequired,
          'Max Videos',
          '50',
          'Maximum number of videos to process (leave empty for all)',
          1,
          null,
          null
        )

      // Website scraping parameters
      case 'start_url':
        return renderTextParam(
          param,
          isRequired,
          'Start URL',
          'https://example.com',
          'Starting URL for website scraping'
        )

      case 'max_pages':
        return renderNumberParam(
          param,
          isRequired,
          'Max Pages',
          '100',
          'Maximum number of pages to scrape',
          1,
          null,
          100
        )

      case 'force_rescrape':
        return renderBooleanParam(
          param,
          isRequired,
          'Force Rescrape',
          'Rescrape pages even if they have already been processed',
          false
        )

      // HubSpot parameters
      case 'limit':
        if (isHubSpotSync) {
          return renderNumberParam(
            param,
            isRequired,
            'Max Deals',
            '100',
            'Maximum number of closed deals to sync',
            1,
            1000,
            100
          )
        }
        // Fall through to default for other job types
        break

      // Generic fallback for unknown parameters
      default:
        return renderTextParam(
          param,
          isRequired,
          param,
          `Enter ${param}`,
          `Parameter: ${param}`
        )
    }
  }

  const renderCredentialsSection = () => {
    if (!needsCredentials) {
      return null
    }

    const sectionTitle = isHubSpotSync ? 'HubSpot Authentication' : 'Google Drive Authentication'
    const noCredsMessage = isHubSpotSync
      ? 'No HubSpot credentials found. Please go to the Credentials tab and add a HubSpot credential first.'
      : 'No Google credentials found. Please go to the Credentials tab and add a Google OAuth credential first.'
    const helpText = isHubSpotSync
      ? 'Select which HubSpot account to use for this task'
      : 'Select which Google account to use for this task'

    if (readOnly) {
      // In read-only mode, just show the selected credential
      const selectedCred = availableCredentials.find(c => c.credential_id === selectedCredential)

      return (
        <div className="mb-4">
          <h6>{sectionTitle}</h6>
          <div className="mb-3">
            <label className="form-label">Selected Credential</label>
            <div className="form-control" style={{ backgroundColor: '#f8f9fa' }}>
              {selectedCred ? selectedCred.credential_name : (selectedCredential || 'None')}
            </div>
          </div>
        </div>
      )
    }

    // Editable mode
    return (
      <div className="mb-4">
        <h6>{sectionTitle}</h6>

        {availableCredentials.length === 0 ? (
          <div className="alert alert-warning">
            <small>{noCredsMessage}</small>
          </div>
        ) : (
          <div className="mb-3">
            <label className="form-label">
              Select Credential <span className="text-danger">*</span>
            </label>
            <select
              className="form-select"
              id="param_credential_id"
              value={selectedCredential}
              onChange={(e) => {
                setSelectedCredential(e.target.value)
                handleParamChange('credential_id', e.target.value)
              }}
              required
            >
              <option value="">Choose a credential...</option>
              {availableCredentials.map((cred) => (
                <option key={cred.credential_id} value={cred.credential_id}>
                  {cred.credential_name}
                </option>
              ))}
            </select>
            <div className="form-text">
              <small className="text-muted">{helpText}</small>
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div>
      {/* OAuth Credential Selection */}
      {renderCredentialsSection()}

      {/* Required Parameters */}
      {selectedTaskType.required_params && selectedTaskType.required_params.length > 0 && (
        <div className="mb-4">
          <h6>Required Parameters:</h6>
          {selectedTaskType.required_params.map((param) => {
            const rendered = renderParameter(param, true)
            return rendered ? (
              <div key={param} className="mb-3">
                {rendered}
              </div>
            ) : null
          })}
        </div>
      )}

      {/* Optional Parameters */}
      {selectedTaskType.optional_params && selectedTaskType.optional_params.length > 0 && (
        <div>
          <h6>Optional Parameters:</h6>
          {selectedTaskType.optional_params.map((param) => {
            const rendered = renderParameter(param, false)
            return rendered ? (
              <div key={param} className="mb-3">
                {rendered}
              </div>
            ) : null
          })}
        </div>
      )}

      {/* Show message if no parameters */}
      {(!selectedTaskType.required_params || selectedTaskType.required_params.length === 0) &&
       (!selectedTaskType.optional_params || selectedTaskType.optional_params.length === 0) && (
        <div className="alert alert-info">
          <Activity size={16} className="me-2" />
          <small>This task type has no configurable parameters</small>
        </div>
      )}
    </div>
  )
}

export default TaskParameters
