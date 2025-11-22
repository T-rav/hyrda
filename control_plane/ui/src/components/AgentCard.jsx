import React from 'react'
import { Users, Shield } from 'lucide-react'

function AgentCard({ agent, onClick }) {
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
          <span className={`stat-badge ${agent.is_public ? 'enabled' : 'disabled'}`}>
            {agent.is_public ? 'Enabled' : 'Disabled'}
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
        </div>
      </div>
    </div>
  )
}

export default AgentCard
