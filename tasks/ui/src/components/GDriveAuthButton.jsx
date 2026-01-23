import React, { useState, useEffect } from 'react'
import { Check, AlertCircle, ExternalLink } from 'lucide-react'
import { logError } from '../utils/logger'

/**
 * Google Drive OAuth Authentication Button Component
 *
 * Handles OAuth flow for Google Drive authentication within task setup.
 * Each task instance gets its own credentials stored on the filesystem.
 */
function GDriveAuthButton({ taskId, credentialId, onAuthComplete }) {
  const [authStatus, setAuthStatus] = useState({ authenticated: false, loading: true })
  const [authError, setAuthError] = useState(null)
  const [authInProgress, setAuthInProgress] = useState(false)

  // Check auth status on mount and when taskId changes
  useEffect(() => {
    if (taskId && credentialId) {
      checkAuthStatus()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId, credentialId])

  if (!credentialId) {
    return (
      <div className="alert alert-warning">
        <AlertCircle size={16} className="me-2" />
        <small>Please select a credential first</small>
      </div>
    )
  }

  const checkAuthStatus = async () => {
    try {
      setAuthStatus({ authenticated: false, loading: true })
      const response = await fetch(`/api/gdrive/auth/status/${taskId}`)
      const data = await response.json()

      setAuthStatus({
        authenticated: data.authenticated,
        loading: false,
        valid: data.valid,
        expired: data.expired
      })

      if (data.authenticated && data.valid) {
        // Notify parent component
        if (onAuthComplete) {
          onAuthComplete(taskId)
        }
      }
    } catch (error) {
      logError('Error checking auth status:', error)
      setAuthStatus({ authenticated: false, loading: false })
      setAuthError('Failed to check authentication status')
    }
  }

  const handleAuthClick = async () => {
    try {
      setAuthInProgress(true)
      setAuthError(null)

      // Initiate OAuth flow
      const response = await fetch('/api/gdrive/auth/initiate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ task_id: taskId, credential_id: credentialId }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to initiate authentication')
      }

      // Open OAuth URL in new window
      const authWindow = window.open(
        data.authorization_url,
        'Google Drive Authentication',
        'width=600,height=700,left=200,top=100'
      )

      // Poll for window closure (user completed auth)
      const pollTimer = setInterval(() => {
        if (authWindow.closed) {
          clearInterval(pollTimer)
          setAuthInProgress(false)
          // Check auth status after window closes
          setTimeout(() => checkAuthStatus(), 1000)
        }
      }, 500)

      // Cleanup if component unmounts
      return () => {
        clearInterval(pollTimer)
        if (authWindow && !authWindow.closed) {
          authWindow.close()
        }
      }
    } catch (error) {
      logError('Error during authentication:', error)
      setAuthError(error.message)
      setAuthInProgress(false)
    }
  }

  if (authStatus.loading) {
    return (
      <div className="alert alert-info">
        <div className="spinner-border spinner-border-sm me-2" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
        <small>Checking authentication status...</small>
      </div>
    )
  }

  if (authStatus.authenticated && authStatus.valid) {
    return (
      <div className="alert alert-success d-flex align-items-center">
        <Check size={16} className="me-2" />
        <div className="flex-grow-1">
          <small>
            <strong>Google Drive Connected</strong>
            <br />
            This task has valid Google Drive credentials
          </small>
        </div>
        <button
          type="button"
          className="btn btn-sm btn-outline-secondary ms-2"
          onClick={handleAuthClick}
          disabled={authInProgress}
        >
          Re-authenticate
        </button>
      </div>
    )
  }

  if (authStatus.authenticated && authStatus.expired) {
    return (
      <div className="alert alert-warning d-flex align-items-center">
        <AlertCircle size={16} className="me-2" />
        <div className="flex-grow-1">
          <small>
            <strong>Credentials Expired</strong>
            <br />
            Please re-authenticate to continue
          </small>
        </div>
        <button
          type="button"
          className="btn btn-sm btn-warning ms-2"
          onClick={handleAuthClick}
          disabled={authInProgress}
        >
          {authInProgress ? 'Authenticating...' : 'Re-authenticate'}
        </button>
      </div>
    )
  }

  return (
    <div>
      <div className="alert alert-info d-flex align-items-center mb-2">
        <AlertCircle size={16} className="me-2" />
        <small>
          Google Drive authentication required to access files and folders.
        </small>
      </div>

      <button
        type="button"
        className="btn btn-primary btn-sm d-flex align-items-center"
        onClick={handleAuthClick}
        disabled={authInProgress}
      >
        <ExternalLink size={16} className="me-1" />
        {authInProgress ? 'Opening Google Login...' : 'Connect Google Drive'}
      </button>

      {authError && (
        <div className="alert alert-danger mt-2 mb-0">
          <small>{authError}</small>
        </div>
      )}

      <div className="form-text mt-2">
        <small className="text-muted">
          You'll be redirected to Google to authorize access.
          This task will use its own set of credentials.
        </small>
      </div>
    </div>
  )
}

export default GDriveAuthButton
