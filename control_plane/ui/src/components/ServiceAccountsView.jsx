import React, { useEffect, useState } from 'react'
import { Plus, RefreshCw, Key, AlertCircle } from 'lucide-react'
import ServiceAccountCard from './ServiceAccountCard'
import CreateServiceAccountModal from './CreateServiceAccountModal'

/**
 * ServiceAccountsView displays and manages service accounts for external API integrations.
 */
function ServiceAccountsView({
  serviceAccounts,
  agents,
  loading,
  onRefresh,
  showCreateModal,
  setShowCreateModal,
  onCreate,
  onRevoke,
  onDelete,
  onToggleActive,
  createdApiKey,
  setCreatedApiKey,
}) {
  const [showRevoked, setShowRevoked] = useState(false)

  const filteredAccounts = showRevoked
    ? serviceAccounts
    : serviceAccounts.filter((account) => !account.is_revoked)

  const hasAccounts = serviceAccounts.length > 0

  return (
    <div className="content-section">
      <div className="section-header">
        <h2>Service Accounts ({filteredAccounts.length})</h2>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {hasAccounts && (
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={showRevoked}
                onChange={(e) => setShowRevoked(e.target.checked)}
              />
              Show Revoked
            </label>
          )}
          <button className="btn-secondary" onClick={onRefresh} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
            Refresh
          </button>
          <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
            <Plus size={16} />
            Create Service Account
          </button>
        </div>
      </div>

      {/* Empty State */}
      {!loading && filteredAccounts.length === 0 && (
        <div className="service-accounts-empty">
          <div className="empty-card">
            <div className="empty-icon-wrapper">
              <Key size={64} strokeWidth={1.5} />
            </div>
            <h3>No Service Accounts Yet</h3>
            <p className="empty-description">
              {showRevoked
                ? 'No revoked service accounts found.'
                : 'Service accounts allow external systems like HubSpot, Salesforce, or custom apps to call agents via API keys.'}
            </p>
            {!showRevoked && (
              <>
                <button
                  className="btn-primary btn-lg"
                  onClick={() => setShowCreateModal(true)}
                  style={{ marginTop: '1.25rem' }}
                >
                  <Plus size={20} />
                  Create Service Account
                </button>
                <div className="empty-features">
                  <div className="feature-item">
                    <span className="feature-icon">🔐</span>
                    <span>Secure API authentication</span>
                  </div>
                  <div className="feature-item">
                    <span className="feature-icon">⚡</span>
                    <span>Per-agent access control</span>
                  </div>
                  <div className="feature-item">
                    <span className="feature-icon">📊</span>
                    <span>Usage tracking & rate limits</span>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && <div className="loading">Loading service accounts...</div>}

      {/* Service Accounts List */}
      {!loading && filteredAccounts.length > 0 && (
        <div className="service-accounts-list">
          {filteredAccounts.map((account) => (
            <ServiceAccountCard
              key={account.id}
              account={account}
              onRevoke={onRevoke}
              onDelete={onDelete}
              onToggleActive={onToggleActive}
            />
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <CreateServiceAccountModal
          agents={agents}
          onClose={() => {
            setShowCreateModal(false)
            setCreatedApiKey(null) // Clear API key when closing
          }}
          onCreate={onCreate}
          createdApiKey={createdApiKey}
          onAcknowledge={() => setCreatedApiKey(null)}
        />
      )}
    </div>
  )
}

export default ServiceAccountsView
