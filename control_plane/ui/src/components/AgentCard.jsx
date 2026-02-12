import React from 'react'
import { Users, Shield, Activity, Key } from 'lucide-react'

function AgentCard({ agent, onClick, usageStats }) {
  return (
    <div className="agent-card clickable" onClick={() => onClick(agent)}>
      <div className="agent-card-header">
        <div className="agent-info">
          <div className="agent-name-header">
            <h3>/{agent.name}</h3>
            {agent.is_system && (
              <span className="stat-badge system">
                <Shield size={10} />
                System
              </span>
            )}
          </div>
          {agent.aliases && agent.aliases.length > 0 && (
            <div className="agent-aliases">
              {agent.aliases.map(alias => (
                <span key={alias} className="badge">{alias}</span>
              ))}
            </div>
          )}
        </div>
        <div>
          <span className={`stat-badge ${agent.is_enabled ? 'enabled' : 'disabled'}`}>
            {agent.is_enabled ? 'Enabled' : 'Disabled'}
          </span>
        </div>
      </div>

      <p className="agent-description">{agent.description}</p>

      <div className="agent-footer">
        <div className="agent-stats">
          {agent.requires_admin && (
            <span className="stat-badge admin">Admin Required</span>
          )}
          <span className="stat-badge users">
            <Users size={14} />
            {agent.authorized_groups === 0 ? 'No groups' : `${agent.authorized_groups} ${agent.authorized_groups === 1 ? 'group' : 'groups'}`}
          </span>
          <span className="stat-badge api-keys">
            <Key size={14} />
            {(!agent.authorized_service_accounts || agent.authorized_service_accounts === 0)
              ? 'No API keys'
              : `${agent.authorized_service_accounts} ${agent.authorized_service_accounts === 1 ? 'API key' : 'API keys'}`}
          </span>
          {usageStats && usageStats.total_invocations > 0 && (
            <span className="stat-badge usage">
              <Activity size={14} />
              {usageStats.total_invocations.toLocaleString()} {usageStats.total_invocations === 1 ? 'call' : 'calls'}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

export default AgentCard
