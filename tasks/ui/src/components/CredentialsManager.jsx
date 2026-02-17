import React, { useState, useEffect } from 'react'
import { Key, Trash2, Plus, AlertCircle, ExternalLink } from 'lucide-react'
import { logError } from '../utils/logger'
import { withBasePath } from '../utils/tokenRefresh'

/**
 * Credentials Manager Component
 *
 * Supports multiple credential types:
 * - Google OAuth: Connect via OAuth flow
 * - HubSpot: Access token + client secret
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
      // Load all credentials (provider field is already in the data)
      const response = await fetch(withBasePath('/api/credentials'))
      const data = await response.json()

      // Use provider from credential data, default to 'google' for legacy credentials
      const allCreds = (data.credentials || []).map(c => ({
        ...c,
        provider: c.provider || 'google'
      }))

      setCredentials(allCreds)
      setError(null)
    } catch (err) {
      logError('Error loading credentials:', err)
      setError('Failed to load credentials')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (cred) => {
    if (!confirm(`Delete credential "${cred.credential_name}"? Tasks using this credential will fail.`)) {
      return
    }

    try {
      const endpoint = cred.provider === 'hubspot'
        ? withBasePath(`/api/hubspot/credentials/${cred.credential_id}`)
        : withBasePath(`/api/credentials/${cred.credential_id}`)

      const response = await fetch(endpoint, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error('Failed to delete credential')
      }

      await loadCredentials()
    } catch (err) {
      logError('Error deleting credential:', err)
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
            <h2>Credentials</h2>
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
            Connect accounts to enable data sync from external services
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
          No credentials configured. Add a credential to start syncing data.
        </div>
      ) : (
        <div className="glass-card">
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Provider</th>
                  <th>Created</th>
                  <th className="text-end">Actions</th>
                </tr>
              </thead>
              <tbody>
                {credentials.map((cred) => (
                  <tr key={cred.credential_id}>
                    <td>
                      <Key size={16} className="me-2 text-primary" />
                      <strong>{cred.credential_name}</strong>
                    </td>
                    <td>
                      <span className={`badge ${cred.provider === 'hubspot' ? 'bg-warning text-dark' : 'bg-primary'}`}>
                        {cred.provider === 'hubspot' ? 'HubSpot' : 'Google'}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-secondary)' }}>
                      {new Date(cred.created_at).toLocaleString()}
                    </td>
                    <td className="text-end">
                      <button
                        className="btn btn-sm btn-outline-danger"
                        onClick={() => handleDelete(cred)}
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
  const [credentialType, setCredentialType] = useState('google')
  const [name, setName] = useState('')
  const [accessToken, setAccessToken] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [error, setError] = useState(null)
  const [authInProgress, setAuthInProgress] = useState(false)
  const [saving, setSaving] = useState(false)

  const handleGoogleOAuth = async () => {
    if (!name) {
      setError('Please enter a credential name first')
      return
    }

    try {
      setAuthInProgress(true)
      setError(null)

      const tempTaskId = `cred_setup_${Date.now()}`

      const response = await fetch(withBasePath('/api/gdrive/auth/initiate'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          task_id: tempTaskId,
          credential_name: name.trim(),
          is_credential_setup: true
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to initiate authentication')
      }

      const authWindow = window.open(
        data.authorization_url,
        'Google Drive Authentication',
        'width=600,height=700,left=200,top=100'
      )

      const pollTimer = setInterval(() => {
        if (authWindow.closed) {
          clearInterval(pollTimer)
          setAuthInProgress(false)
          onSuccess()
        }
      }, 500)

    } catch (err) {
      logError('Error during OAuth:', err)
      setError(err.message)
      setAuthInProgress(false)
    }
  }

  const handleHubSpotSave = async () => {
    if (!name) {
      setError('Please enter a credential name')
      return
    }
    if (!accessToken) {
      setError('Please enter the access token')
      return
    }
    if (!clientSecret) {
      setError('Please enter the client secret')
      return
    }

    try {
      setSaving(true)
      setError(null)

      const response = await fetch(withBasePath('/api/hubspot/credentials'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          credential_name: name.trim(),
          access_token: accessToken.trim(),
          client_secret: clientSecret.trim(),
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to save credentials')
      }

      onSuccess()
    } catch (err) {
      logError('Error saving HubSpot credentials:', err)
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      {/* Modal backdrop */}
      <div
        className="modal-backdrop show"
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          zIndex: 1040
        }}
        onClick={onClose}
      ></div>

      {/* Modal dialog */}
      <div
        className="modal show"
        tabIndex="-1"
        role="dialog"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          overflow: 'auto',
          zIndex: 1050
        }}
      >
        <div className="modal-dialog" role="document" style={{ margin: 0, maxWidth: '600px', width: '90%' }}>
          <div className="modal-content glass-card">
            <div className="modal-header">
              <div className="header-title">
                <Key size={20} />
                <h5 className="modal-title">Add Credential</h5>
              </div>
              <button
                type="button"
                className="btn-close"
                onClick={onClose}
                aria-label="Close"
              ></button>
            </div>
            <div className="modal-body">
              {/* Credential Type Selector */}
              <div className="mb-4">
                <label className="form-label">Credential Type</label>
                <div className="btn-group w-100" role="group">
                  <button
                    type="button"
                    className={`btn ${credentialType === 'google' ? 'btn-primary' : 'btn-outline-primary'}`}
                    onClick={() => setCredentialType('google')}
                    disabled={authInProgress || saving}
                  >
                    Google OAuth
                  </button>
                  <button
                    type="button"
                    className={`btn ${credentialType === 'hubspot' ? 'btn-warning' : 'btn-outline-warning'}`}
                    onClick={() => setCredentialType('hubspot')}
                    disabled={authInProgress || saving}
                  >
                    HubSpot
                  </button>
                </div>
              </div>

              {/* Credential Name (shared) */}
              <div className="mb-3">
                <label className="form-label">Credential Name</label>
                <input
                  type="text"
                  className="form-control"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={credentialType === 'google' ? 'e.g., Work Google Account' : 'e.g., 8th Light HubSpot'}
                  required
                  disabled={authInProgress || saving}
                />
              </div>

              {/* Google OAuth Instructions */}
              {credentialType === 'google' && (
                <div className="alert alert-info">
                  <AlertCircle size={16} className="me-2" />
                  <small>
                    Click "Connect Google" to sign in with your Google account and authorize access.
                  </small>
                </div>
              )}

              {/* HubSpot Fields */}
              {credentialType === 'hubspot' && (
                <>
                  <div className="mb-3">
                    <label className="form-label">Access Token</label>
                    <input
                      type="password"
                      className="form-control"
                      value={accessToken}
                      onChange={(e) => setAccessToken(e.target.value)}
                      placeholder="Enter HubSpot access token"
                      required
                      disabled={saving}
                    />
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Client Secret</label>
                    <input
                      type="password"
                      className="form-control"
                      value={clientSecret}
                      onChange={(e) => setClientSecret(e.target.value)}
                      placeholder="Enter HubSpot client secret"
                      required
                      disabled={saving}
                    />
                  </div>
                  <div className="alert alert-info">
                    <AlertCircle size={16} className="me-2" />
                    <small>
                      Find these in HubSpot: Settings → Integrations → Private Apps
                    </small>
                  </div>
                </>
              )}

              {error && (
                <div className="alert alert-danger mb-3">
                  <AlertCircle size={16} className="me-2" />
                  {error}
                </div>
              )}
            </div>
            <div className="modal-footer">
              {authInProgress ? (
                <div className="alert alert-info mb-0 w-100">
                  <div className="spinner-border spinner-border-sm me-2" role="status"></div>
                  Waiting for Google authentication...
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-secondary float-end"
                    onClick={onClose}
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <>
                  {credentialType === 'google' ? (
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={handleGoogleOAuth}
                      disabled={!name}
                    >
                      <ExternalLink size={16} className="me-1" />
                      Connect Google
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-warning"
                      onClick={handleHubSpotSave}
                      disabled={!name || !accessToken || !clientSecret || saving}
                    >
                      {saving ? (
                        <>
                          <span className="spinner-border spinner-border-sm me-1" role="status"></span>
                          Saving...
                        </>
                      ) : (
                        <>
                          <Key size={16} className="me-1" />
                          Save HubSpot Credentials
                        </>
                      )}
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn-outline-secondary"
                    onClick={onClose}
                    disabled={saving}
                  >
                    Cancel
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

export default CredentialsManager
