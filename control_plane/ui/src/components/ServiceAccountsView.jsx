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

  return (
    <div className="view-container">
      {/* Header */}
      <div className="view-header">
        <div className="view-title">
          <Key size={28} />
          <h2>Service Accounts</h2>
          <span className="badge badge-blue">{filteredAccounts.length}</span>
        </div>
        <div className="view-actions">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={showRevoked}
              onChange={(e) => setShowRevoked(e.target.checked)}
            />
            Show Revoked
          </label>
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

      {/* Info Banner */}
      <div className="alert alert-info">
        <AlertCircle size={20} />
        <div>
          <strong>Service Accounts for External Integrations</strong>
          <p>
            Create API keys for external systems (HubSpot, Salesforce, custom apps) to call agents
            via HTTP. Separate from internal service-to-service tokens.
          </p>
        </div>
      </div>

      {/* Empty State */}
      {!loading && filteredAccounts.length === 0 && (
        <div className="empty-state">
          <Key size={48} className="empty-icon" />
          <h3>No Service Accounts</h3>
          <p>
            {showRevoked
              ? 'No revoked service accounts found.'
              : 'Create a service account to allow external systems to authenticate with API keys.'}
          </p>
          {!showRevoked && (
            <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
              <Plus size={16} />
              Create First Service Account
            </button>
          )}
        </div>
      )}

      {/* Loading State */}
      {loading && <div className="loading">Loading service accounts...</div>}

      {/* Service Accounts Grid */}
      {!loading && filteredAccounts.length > 0 && (
        <div className="cards-grid">
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
