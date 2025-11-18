import React from 'react'
import { Users } from 'lucide-react'

function AgentCard({ agent, onClick }) {
  return (
    <div className="agent-card" onClick={() => onClick(agent)} style={{ cursor: 'pointer' }}>
      <div className="agent-card-header">
        <div className="agent-info">
          <h3>/{agent.name}</h3>
          {agent.aliases && agent.aliases.length > 0 && (
            <div className="agent-aliases">
              {agent.aliases.map(alias => (
                <span key={alias} className="badge">{alias}</span>
              ))}
            </div>
          )}
        </div>
        <div className={`agent-status ${agent.is_public ? 'public' : 'private'}`}>
          {agent.is_public ? 'Public' : 'Private'}
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
            {agent.authorized_users === 0 ? 'All users' : `${agent.authorized_users} users`}
          </span>
        </div>
      </div>
    </div>
  )
}

export default AgentCard
