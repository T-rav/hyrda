import React, { useState, useEffect } from 'react'
import { Shield, Users, Activity, Bot, ChevronRight } from 'lucide-react'
import './App.css'

function App() {
  const [activeTab, setActiveTab] = useState('agents')
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    document.title = 'InsightMesh - Control Plane'
    fetchAgents()
  }, [])

  const fetchAgents = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/agents')
      if (!response.ok) throw new Error('Failed to fetch agents')
      const data = await response.json()
      setAgents(data.agents || [])
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <div className="header-title">
            <Shield className="header-icon" size={28} />
            <h1>InsightMesh Control Plane</h1>
          </div>
          <nav className="header-nav">
            <button
              className={`nav-link ${activeTab === 'agents' ? 'active' : ''}`}
              onClick={() => setActiveTab('agents')}
            >
              <Bot size={20} />
              Agents
            </button>
            <button
              className={`nav-link ${activeTab === 'users' ? 'active' : ''}`}
              onClick={() => setActiveTab('users')}
            >
              <Users size={20} />
              Users
            </button>
            <a
              href="http://localhost:8080/health"
              target="_blank"
              rel="noopener noreferrer"
              className="nav-link external"
            >
              <Activity size={20} />
              Health
            </a>
          </nav>
        </div>
      </header>

      <main className="main-content">
        {activeTab === 'agents' && (
          <AgentsView
            agents={agents}
            loading={loading}
            error={error}
            onRefresh={fetchAgents}
          />
        )}
        {activeTab === 'users' && <UsersView />}
      </main>
    </div>
  )
}

function AgentsView({ agents, loading, error, onRefresh }) {
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
          Refresh
        </button>
      </div>

      <div className="agents-grid">
        {agents.map(agent => (
          <AgentCard key={agent.name} agent={agent} />
        ))}
      </div>

      {agents.length === 0 && (
        <div className="empty-state">
          <Bot size={48} />
          <p>No agents registered</p>
        </div>
      )}
    </div>
  )
}

function AgentCard({ agent }) {
  return (
    <div className="agent-card">
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
        <button className="btn-link">
          Manage <ChevronRight size={16} />
        </button>
      </div>
    </div>
  )
}

function UsersView() {
  return (
    <div className="content-section">
      <div className="section-header">
        <h2>User Management</h2>
      </div>
      <div className="empty-state">
        <Users size={48} />
        <p>User management coming soon</p>
      </div>
    </div>
  )
}

export default App
