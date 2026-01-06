import React from 'react'
import { Key, Shield, Ban, Trash2, Calendar, Activity, Users } from 'lucide-react'

/**
 * ServiceAccountCard component displays a single service account.
 */
function ServiceAccountCard({ account, onRevoke, onDelete, onToggleActive }) {

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

  const allowedAgentsDisplay =
    account.allowed_agents === null || account.allowed_agents.length === 0
      ? 'No agents'
      : account.allowed_agents.join(', ')

  return (
    <div className={`service-account-card ${statusClass}`}>
      {/* Card Header - Always Visible */}
      <div className="card-header" style={{ cursor: 'default' }}>
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
                <span style={{
                  maxWidth: '300px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap'
                }} title={allowedAgentsDisplay}>
                  {allowedAgentsDisplay}
                </span>
              </div>
              {account.last_used_at && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                  <Calendar size={14} />
                  <span>Last used {new Date(account.last_used_at).toLocaleDateString()}</span>
                </div>
              )}
            </div>
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
    </div>
  )
}

export default ServiceAccountCard
