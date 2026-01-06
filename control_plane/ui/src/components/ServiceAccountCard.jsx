import React from 'react'
import { Key, Shield, Ban, Trash2, Activity } from 'lucide-react'

/**
 * ServiceAccountCard component displays a single service account.
 * Styled to match GroupCard design pattern.
 */
function ServiceAccountCard({ account, onRevoke, onDelete, onToggleActive }) {
  const isExpired = account.expires_at && new Date(account.expires_at) < new Date()

  const statusClass = account.is_revoked
    ? 'revoked'
    : !account.is_active
    ? 'inactive'
    : isExpired
    ? 'expired'
    : 'active'

  const statusText = account.is_revoked
    ? 'Revoked'
    : !account.is_active
    ? 'Inactive'
    : isExpired
    ? 'Expired'
    : 'Active'

  const statusStyle = {
    active: { background: '#ecfdf5', color: '#047857', border: '1px solid #10b981' },
    inactive: { background: '#fef3c7', color: '#92400e', border: '1px solid #fbbf24' },
    revoked: { background: '#fee2e2', color: '#991b1b', border: '1px solid #ef4444' },
    expired: { background: '#f3f4f6', color: '#374151', border: '1px solid #9ca3af' },
  }

  const allowedAgentsDisplay =
    account.allowed_agents === null || account.allowed_agents.length === 0
      ? 'No agents'
      : account.allowed_agents.join(', ')

  const handleDelete = () => {
    if (
      window.confirm(
        `Are you sure you want to permanently delete "${account.name}"? This cannot be undone.`
      )
    ) {
      onDelete(account.id, account.name)
    }
  }

  return (
    <div className="service-account-card">
      <div className="service-account-header">
        <div>
          <h3>{account.name}</h3>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.25rem' }}>
            <span className="stat-badge" style={statusStyle[statusClass]}>
              {statusText}
            </span>
            <code className="api-key-prefix">{account.api_key_prefix}...</code>
          </div>
        </div>
        <div className="service-account-stats">
          <span className="stat-badge">
            <Activity size={14} />
            {account.total_requests} requests
          </span>
          <span className="stat-badge">
            <Shield size={14} />
            {account.rate_limit}/hour
          </span>
        </div>
      </div>

      {account.description && <p className="service-account-description">{account.description}</p>}

      <div className="service-account-agents">
        <span style={{ color: '#64748b', fontSize: '0.875rem', fontWeight: 500 }}>
          Allowed Agents:
        </span>
        <span
          style={{
            fontSize: '0.875rem',
            color: '#1e293b',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={allowedAgentsDisplay}
        >
          {allowedAgentsDisplay}
        </span>
      </div>

      <div className="service-account-footer">
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {!account.is_revoked && account.is_active && (
            <button
              className="btn-link"
              onClick={() => onToggleActive(account.id, true)}
              title="Deactivate API key"
            >
              <Shield size={16} />
              Deactivate
            </button>
          )}
          {!account.is_revoked && !account.is_active && (
            <button
              className="btn-link"
              onClick={() => onToggleActive(account.id, false)}
              title="Activate API key"
            >
              <Shield size={16} />
              Activate
            </button>
          )}
          {!account.is_revoked && (
            <button
              className="btn-link"
              onClick={() => onRevoke(account.id)}
              title="Revoke API Key (cannot be undone)"
              style={{ color: '#dc2626' }}
            >
              <Ban size={16} />
              Revoke
            </button>
          )}
        </div>
        <button
          className="btn-link"
          onClick={handleDelete}
          title="Delete permanently"
          style={{ color: '#dc2626' }}
        >
          <Trash2 size={16} />
          Delete
        </button>
      </div>
    </div>
  )
}

export default ServiceAccountCard
