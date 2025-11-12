import React, { useState, useEffect } from 'react'
import { Key, Trash2, Plus, X, AlertCircle, Check } from 'lucide-react'

/**
 * Credentials Manager Component
 *
 * Manages Google OAuth credentials for Google Drive tasks.
 * Each credential represents a different Google account that can access different files.
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
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h2 className="mb-1">
            <Key size={28} className="me-2" />
            Google Drive Credentials
          </h2>
          <p className="text-muted">
            Manage Google OAuth credentials for accessing different Google Drive accounts
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setShowAddModal(true)}
        >
          <Plus size={18} className="me-1" />
          Add Credential
        </button>
      </div>

      {error && (
        <div className="alert alert-danger">
          <AlertCircle size={16} className="me-2" />
          {error}
        </div>
      )}

      {credentials.length === 0 ? (
        <div className="alert alert-info">
          <AlertCircle size={16} className="me-2" />
          No credentials configured. Add a credential to start using Google Drive ingestion.
        </div>
      ) : (
        <div className="card">
          <div className="card-body">
            <table className="table table-hover">
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
                    <td className="text-muted">
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
  const [credentials, setCredentials] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/credentials', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: name.trim(),
          credentials: credentials.trim(),
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to add credential')
      }

      onSuccess()
    } catch (err) {
      console.error('Error adding credential:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = (e) => {
    const file = e.target.files[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (event) => {
      setCredentials(event.target.result)
      if (!name) {
        setName(file.name.replace('.json', ''))
      }
    }
    reader.readAsText(file)
  }

  return (
    <>
      <div className="modal-backdrop fade show" onClick={onClose}></div>
      <div className="modal fade show d-block" tabIndex="-1">
        <div className="modal-dialog modal-lg">
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
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="alert alert-info">
                  <AlertCircle size={16} className="me-2" />
                  <small>
                    <strong>How to get credentials:</strong><br />
                    1. Go to <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer">Google Cloud Console</a><br />
                    2. Create OAuth 2.0 Client ID (Application type: Web application)<br />
                    3. Add authorized redirect URI: <code>http://localhost:5001/api/gdrive/auth/callback</code><br />
                    4. Download the JSON file
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
                  />
                  <div className="form-text">
                    Give this credential a memorable name
                  </div>
                </div>

                <div className="mb-3">
                  <label className="form-label">Upload Credentials File</label>
                  <input
                    type="file"
                    className="form-control"
                    accept=".json,application/json"
                    onChange={handleFileUpload}
                  />
                  <div className="form-text">
                    Upload the credentials.json file from Google Cloud Console
                  </div>
                </div>

                <div className="mb-3">
                  <label className="form-label">Or Paste JSON Content</label>
                  <textarea
                    className="form-control font-monospace"
                    rows="8"
                    value={credentials}
                    onChange={(e) => setCredentials(e.target.value)}
                    placeholder='{"web":{"client_id":"...","client_secret":"..."}}'
                    required
                  ></textarea>
                  <div className="form-text">
                    Paste the content of your credentials.json file
                  </div>
                </div>

                {error && (
                  <div className="alert alert-danger">
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
                  disabled={loading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={loading || !name || !credentials}
                >
                  {loading ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                      Adding...
                    </>
                  ) : (
                    <>
                      <Check size={16} className="me-1" />
                      Add Credential
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </>
  )
}

export default CredentialsManager
