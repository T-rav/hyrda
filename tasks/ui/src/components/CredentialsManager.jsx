import React, { useState, useEffect } from 'react'
import { Key, Trash2, Plus, X, AlertCircle, Check, ExternalLink } from 'lucide-react'

/**
 * Credentials Manager Component
 *
 * Simple OAuth-based credential management - no file uploads needed!
 * Just enter a name and click "Connect Google" to set up credentials.
 */
function CredentialsManager() {
  const [credentials, setCredentials] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showAddModal, setShowAddModal] = useState(false)

  useEffect(() => {
    loadCredentials()
  }, [])

  const loadCredentials = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/credentials')
      const data = await response.json()
      setCredentials(data.credentials || [])
      setError(null)
    } catch (err) {
      console.error('Error loading credentials:', err)
      setError('Failed to load credentials')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (credId) => {
    if (!confirm(`Delete credential "${credId}"? Tasks using this credential will fail.`)) {
      return
    }

    try {
      const response = await fetch(`/api/credentials/${credId}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error('Failed to delete credential')
      }

      await loadCredentials()
    } catch (err) {
      console.error('Error deleting credential:', err)
      alert('Failed to delete credential: ' + err.message)
    }
  }

  if (loading) {
    return (
      <div className="container-fluid py-4">
        <div className="text-center">
          <div className="spinner-border" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="container-fluid py-4">
      <div className="glass-card mb-4">
        <div className="card-header">
          <div className="header-title">
            <Key size={28} />
            <h2>Google Drive Credentials</h2>
          </div>
          <button
            className="btn btn-outline-success"
            onClick={() => setShowAddModal(true)}
          >
            <Plus size={18} className="me-1" />
            Add Credential
          </button>
        </div>
        <div className="card-body">
          <p style={{ color: 'var(--text-primary)', opacity: 0.9 }}>
            Connect different Google accounts to access different files
          </p>
        </div>
      </div>

      {error && (
        <div className="alert alert-danger" style={{ color: '#721c24' }}>
          <AlertCircle size={16} className="me-2" />
          {error}
        </div>
      )}

      {credentials.length === 0 ? (
        <div className="alert alert-info" style={{ color: '#004085', backgroundColor: 'rgba(209, 236, 241, 0.3)' }}>
          <AlertCircle size={16} className="me-2" />
          No credentials configured. Add a credential to start using Google Drive ingestion.
        </div>
      ) : (
        <div className="glass-card">
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Created</th>
                  <th className="text-end">Actions</th>
                </tr>
              </thead>
              <tbody>
                {credentials.map((cred) => (
                  <tr key={cred.id}>
                    <td>
                      <Key size={16} className="me-2 text-primary" />
                      <strong>{cred.name}</strong>
                    </td>
                    <td style={{ color: 'var(--text-secondary)' }}>
                      {new Date(cred.created_at * 1000).toLocaleString()}
                    </td>
                    <td className="text-end">
                      <button
                        className="btn btn-sm btn-outline-danger"
                        onClick={() => handleDelete(cred.id)}
                      >
                        <Trash2 size={14} className="me-1" />
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showAddModal && (
        <AddCredentialModal
          onClose={() => setShowAddModal(false)}
          onSuccess={() => {
            setShowAddModal(false)
            loadCredentials()
          }}
        />
      )}
    </div>
  )
}

function AddCredentialModal({ onClose, onSuccess }) {
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [credentialId, setCredentialId] = useState(null)
  const [authInProgress, setAuthInProgress] = useState(false)

  // Generate credential ID from name
  useEffect(() => {
    if (name) {
      const id = name.toLowerCase().replace(/[^a-z0-9]/g, '_')
      setCredentialId(id)
    }
  }, [name])

  const handleOAuthClick = async () => {
    if (!name || !credentialId) {
      setError('Please enter a credential name first')
      return
    }

    try {
      setAuthInProgress(true)
      setError(null)

      // Initiate OAuth flow with a temporary task ID for credential setup
      const tempTaskId = `cred_setup_${credentialId}_${Date.now()}`

      const response = await fetch('/api/gdrive/auth/initiate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          task_id: tempTaskId,
          credential_id: credentialId,
          is_credential_setup: true  // Flag to indicate this is credential setup
        }),
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

      // Poll for window closure
      const pollTimer = setInterval(() => {
        if (authWindow.closed) {
          clearInterval(pollTimer)
          setAuthInProgress(false)
          // On success, save the credential name to our system
          saveCredentialName()
        }
      }, 500)

    } catch (err) {
      console.error('Error during OAuth:', err)
      setError(err.message)
      setAuthInProgress(false)
    }
  }

  const saveCredentialName = async () => {
    try {
      setLoading(true)

      // Just save the metadata - the OAuth flow already saved the actual credentials
      const response = await fetch('/api/credentials', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: name.trim(),
          id: credentialId,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to save credential')
      }

      onSuccess()
    } catch (err) {
      console.error('Error saving credential:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="modal-backdrop fade show" onClick={onClose}></div>
      <div className="modal fade show d-block" tabIndex="-1">
        <div className="modal-dialog" style={{ maxWidth: '100%', margin: '1rem' }}>
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">
                <Key size={20} className="me-2" />
                Add Google OAuth Credential
              </h5>
              <button
                type="button"
                className="btn-close"
                onClick={onClose}
                aria-label="Close"
              ></button>
            </div>
            <div className="modal-body">
              <div className="alert alert-info">
                <AlertCircle size={16} className="me-2" />
                <small>
                  <strong>Simple setup:</strong><br />
                  1. Enter a name for this credential<br />
                  2. Click "Connect Google Drive"<br />
                  3. Sign in with your Google account<br />
                  That's it - no files to upload!
                </small>
              </div>

              <div className="mb-3">
                <label className="form-label">Credential Name</label>
                <input
                  type="text"
                  className="form-control"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Personal Account, Work Account, Client XYZ"
                  required
                  disabled={authInProgress || loading}
                />
                <div className="form-text">
                  Give this credential a memorable name
                </div>
              </div>

              {!authInProgress && !loading && (
                <button
                  type="button"
                  className="btn btn-primary w-100"
                  onClick={handleOAuthClick}
                  disabled={!name}
                >
                  <ExternalLink size={16} className="me-1" />
                  Connect Google Drive
                </button>
              )}

              {authInProgress && (
                <div className="alert alert-info mb-0">
                  <div className="spinner-border spinner-border-sm me-2" role="status"></div>
                  Waiting for Google authentication...
                </div>
              )}

              {loading && (
                <div className="alert alert-info mb-0">
                  <div className="spinner-border spinner-border-sm me-2" role="status"></div>
                  Saving credential...
                </div>
              )}

              {error && (
                <div className="alert alert-danger mt-3 mb-0">
                  <AlertCircle size={16} className="me-2" />
                  {error}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-outline-secondary"
                onClick={onClose}
                disabled={authInProgress || loading}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

export default CredentialsManager
