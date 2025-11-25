import React, { useState } from 'react'
import { Bot, RefreshCw } from 'lucide-react'
import AgentCard from './AgentCard'
import ManageAgentAccessModal from './ManageAgentAccessModal'

function AgentsView({ agents, groups, loading, error, usageStats, onRefresh, onForceRefresh, selectedAgent, selectedAgentDetails, setSelectedAgent, onGrantToGroup, onRevokeFromGroup, onToggle }) {
  const [showManageAccess, setShowManageAccess] = useState(false)

  const handleAgentClick = (agent) => {
    setSelectedAgent(agent)
    setShowManageAccess(true)
  }

  if (loading) {
    return <div className="loading">Loading agents...</div>
  }

  if (error) {
    return (
      <div className="error-container">
        <p className="error">Error: {error}</p>
        <button onClick={onRefresh} className="btn-primary">
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="content-section">
      <div className="section-header">
        <h2>Registered Agents ({agents.length})</h2>
        <button onClick={onRefresh} className="btn-secondary">
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      <div className="agents-grid">
        {agents.map(agent => (
          <AgentCard
            key={agent.name}
            agent={agent}
            onClick={handleAgentClick}
            usageStats={usageStats[agent.name]}
          />
        ))}
      </div>

      {agents.length === 0 && (
        <div className="empty-state">
          <Bot size={48} />
          <p>No agents registered</p>
        </div>
      )}

      {showManageAccess && selectedAgent && selectedAgentDetails && (
        <ManageAgentAccessModal
          agent={selectedAgentDetails}
          groups={groups}
          onClose={() => {
            setShowManageAccess(false)
            setSelectedAgent(null)
          }}
          onGrantToGroup={onGrantToGroup}
          onRevokeFromGroup={onRevokeFromGroup}
          onToggle={onToggle}
        />
      )}
    </div>
  )
}

export default AgentsView
