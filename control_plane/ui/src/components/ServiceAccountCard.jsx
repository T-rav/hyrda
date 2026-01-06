import React, { useState } from 'react'
import { Key, Shield, Ban, Trash2, Edit, Calendar, Activity } from 'lucide-react'

/**
 * ServiceAccountCard component displays a single service account.
 */
function ServiceAccountCard({ account, onRevoke, onDelete, onToggleActive }) {
  const [expanded, setExpanded] = useState(false)

  const isExpired = account.expires_at && new Date(account.expires_at) < new Date()

  const statusClass = account.is_revoked
    ? 'status-revoked'
    : !account.is_active
    ? 'status-inactive'
    : isExpired
    ? 'status-expired'
    : 'status-active'

  const statusText = account.is_revoked
    ? 'Revoked'
    : !account.is_active
    ? 'Inactive'
    : isExpired
    ? 'Expired'
    : 'Active'

  return (
    <div className={`card ${statusClass}`}>
      <div className="card-header" onClick={() => setExpanded(!expanded)}>
        <div className="card-title">
          <Key size={20} />
          <h3>{account.name}</h3>
          <span className={`badge ${statusClass}`}>{statusText}</span>
        </div>
        <div className="card-actions" onClick={(e) => e.stopPropagation()}>
          {!account.is_revoked && (
            <button
              className="btn-secondary btn-sm"
              onClick={() => onToggleActive(account.id, account.is_active)}
              title={account.is_active ? 'Deactivate' : 'Activate'}
            >
              <Shield size={16} />
              {account.is_active ? 'Deactivate' : 'Activate'}
            </button>
          )}
          {!account.is_revoked && (
            <button
              className="btn-danger btn-sm"
              onClick={() => onRevoke(account.id)}
              title="Revoke API Key"
            >
              <Ban size={16} />
              Revoke
            </button>
          )}
          <button
            className="btn-danger btn-sm"
            onClick={() => onDelete(account.id, account.name)}
            title="Delete permanently"
          >
            <Trash2 size={16} />
            Delete
          </button>
        </div>
      </div>

      {expanded && (
        <div className="card-body">
          <div className="info-grid">
            {/* Description */}
            {account.description && (
              <div className="info-row">
                <label>Description:</label>
                <span>{account.description}</span>
              </div>
            )}

            {/* API Key Prefix */}
            <div className="info-row">
              <label>API Key Prefix:</label>
              <code className="code-inline">{account.api_key_prefix}...</code>
            </div>

            {/* Scopes */}
            <div className="info-row">
              <label>Scopes:</label>
              <div className="badge-list">
                {account.scopes?.split(',').map((scope) => (
                  <span key={scope} className="badge badge-blue">
                    {scope.trim()}
                  </span>
                ))}
              </div>
            </div>

            {/* Allowed Agents */}
            <div className="info-row">
              <label>Allowed Agents:</label>
              {account.allowed_agents === null ? (
                <span className="text-muted">All agents</span>
              ) : (
                <div className="badge-list">
                  {account.allowed_agents.map((agent) => (
                    <span key={agent} className="badge badge-purple">
                      {agent}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Rate Limit */}
            <div className="info-row">
              <label>Rate Limit:</label>
              <span>{account.rate_limit} requests/hour</span>
            </div>

            {/* Usage Stats */}
            <div className="info-row">
              <label>
                <Activity size={16} />
                Usage:
              </label>
              <span>
                {account.total_requests} total requests
                {account.last_used_at && (
                  <span className="text-muted">
                    {' '}
                    • Last used: {new Date(account.last_used_at).toLocaleString()}
                  </span>
                )}
                {account.last_request_ip && (
                  <span className="text-muted"> • IP: {account.last_request_ip}</span>
                )}
              </span>
            </div>

            {/* Expiration */}
            {account.expires_at && (
              <div className="info-row">
                <label>
                  <Calendar size={16} />
                  Expires:
                </label>
                <span className={isExpired ? 'text-danger' : ''}>
                  {new Date(account.expires_at).toLocaleString()}
                  {isExpired && ' (EXPIRED)'}
                </span>
              </div>
            )}

            {/* Created By */}
            <div className="info-row">
              <label>Created By:</label>
              <span>{account.created_by || 'Unknown'}</span>
            </div>

            {/* Created At */}
            <div className="info-row">
              <label>Created:</label>
              <span>{new Date(account.created_at).toLocaleString()}</span>
            </div>

            {/* Revocation Info */}
            {account.is_revoked && (
              <>
                <div className="info-row">
                  <label>Revoked At:</label>
                  <span>{new Date(account.revoked_at).toLocaleString()}</span>
                </div>
                <div className="info-row">
                  <label>Revoked By:</label>
                  <span>{account.revoked_by}</span>
                </div>
                {account.revoke_reason && (
                  <div className="info-row">
                    <label>Reason:</label>
                    <span className="text-danger">{account.revoke_reason}</span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default ServiceAccountCard
