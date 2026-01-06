import React, { useState } from 'react'
import { Key, Shield, Ban, Trash2, Calendar, Activity, ChevronDown, ChevronUp, Users } from 'lucide-react'

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

  const allowedAgentsText =
    account.allowed_agents === null || account.allowed_agents.length === 0
      ? 'No agents'
      : account.allowed_agents.length === 1
      ? '1 agent'
      : `${account.allowed_agents.length} agents`

  return (
    <div className={`service-account-card ${statusClass}`}>
      {/* Collapsed Header - Always Visible */}
      <div className="card-header" onClick={() => setExpanded(!expanded)} style={{ cursor: 'pointer' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', flex: 1 }}>
          <Key size={24} style={{ flexShrink: 0, marginTop: '0.25rem' }} />

          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Name + Status */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
              <h3 style={{ margin: 0, fontSize: '1.125rem', fontWeight: 600 }}>{account.name}</h3>
              <span className={`badge ${statusClass}`}>{statusText}</span>
            </div>

            {/* API Key Prefix */}
            <div style={{ marginBottom: '0.5rem' }}>
              <code style={{
                fontSize: '0.875rem',
                background: 'rgba(0,0,0,0.05)',
                padding: '0.25rem 0.5rem',
                borderRadius: '0.25rem',
                fontFamily: 'monospace'
              }}>
                {account.api_key_prefix}...
              </code>
            </div>

            {/* Description (if exists) */}
            {account.description && (
              <p style={{
                margin: '0.5rem 0',
                fontSize: '0.875rem',
                color: '#64748b',
                lineHeight: 1.5
              }}>
                {account.description}
              </p>
            )}

            {/* Key Metrics Row */}
            <div style={{
              display: 'flex',
              gap: '1.5rem',
              fontSize: '0.875rem',
              color: '#64748b',
              marginTop: '0.75rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <Activity size={14} />
                <span>{account.total_requests} requests</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <Shield size={14} />
                <span>{account.rate_limit}/hour</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <Users size={14} />
                <span>{allowedAgentsText}</span>
              </div>
              {account.last_used_at && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                  <Calendar size={14} />
                  <span>Last used {new Date(account.last_used_at).toLocaleDateString()}</span>
                </div>
              )}
            </div>
          </div>

          {/* Expand/Collapse Indicator */}
          <div style={{ flexShrink: 0, marginTop: '0.25rem' }}>
            {expanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </div>
        </div>
      </div>

      {/* Action Buttons - Always Visible */}
      <div className="card-actions" style={{ padding: '0.75rem 1rem', borderTop: '1px solid rgba(0,0,0,0.1)', display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
        {!account.is_revoked && account.is_active && (
          <button
            className="btn-secondary btn-sm"
            onClick={() => onToggleActive(account.id, true)}
            title="Deactivate API key"
          >
            <Shield size={16} />
            Deactivate
          </button>
        )}
        {!account.is_revoked && !account.is_active && (
          <button
            className="btn-secondary btn-sm"
            onClick={() => onToggleActive(account.id, false)}
            title="Activate API key"
          >
            <Shield size={16} />
            Activate
          </button>
        )}
        {!account.is_revoked && (
          <button
            className="btn-danger btn-sm"
            onClick={() => onRevoke(account.id)}
            title="Revoke API Key (cannot be undone)"
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
