import React, { useState, useEffect } from 'react'
import { Shield, Users, Activity, Bot, UserPlus, Plus, X } from 'lucide-react'
import './App.css'

function App() {
  const [activeTab, setActiveTab] = useState('agents')
  const [agents, setAgents] = useState([])
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreateGroup, setShowCreateGroup] = useState(false)

  useEffect(() => {
    document.title = 'InsightMesh - Control Plane'
    fetchAgents()
    fetchGroups()
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

  const fetchGroups = async () => {
    try {
      const response = await fetch('/api/groups')
      if (!response.ok) throw new Error('Failed to fetch groups')
      const data = await response.json()
      setGroups(data.groups || [])
    } catch (err) {
      console.error('Error fetching groups:', err)
      // Mock data for now
      setGroups([
        { group_name: 'analysts', display_name: 'Data Analysts', description: 'Team members who analyze data', user_count: 3 },
        { group_name: 'sales', display_name: 'Sales Team', description: 'Sales representatives', user_count: 5 },
      ])
    }
  }

  const createGroup = async (groupData) => {
    try {
      const response = await fetch('/api/groups', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(groupData)
      })
      if (!response.ok) throw new Error('Failed to create group')
      fetchGroups()
      setShowCreateGroup(false)
    } catch (err) {
      alert(`Error: ${err.message}`)
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
              className={`nav-link ${activeTab === 'groups' ? 'active' : ''}`}
              onClick={() => setActiveTab('groups')}
            >
              <Users size={20} />
              Groups
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
        {activeTab === 'groups' && (
          <GroupsView
            groups={groups}
            onRefresh={fetchGroups}
            showCreateGroup={showCreateGroup}
            setShowCreateGroup={setShowCreateGroup}
            onCreateGroup={createGroup}
          />
        )}
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
      </div>
    </div>
  )
}

function GroupsView({ groups, onRefresh, showCreateGroup, setShowCreateGroup, onCreateGroup }) {
  return (
    <div className="content-section">
      <div className="section-header">
        <h2>Permission Groups ({groups.length})</h2>
        <div>
          <button onClick={onRefresh} className="btn-secondary">
            Refresh
          </button>
          <button
            onClick={() => setShowCreateGroup(true)}
            className="btn-primary"
            style={{ marginLeft: '0.5rem' }}
          >
            <Plus size={16} />
            Create Group
          </button>
        </div>
      </div>

      {showCreateGroup && (
        <CreateGroupModal
          onClose={() => setShowCreateGroup(false)}
          onCreate={onCreateGroup}
        />
      )}

      <div className="groups-list">
        {groups.map(group => (
          <GroupCard key={group.group_name} group={group} />
        ))}
      </div>

      {groups.length === 0 && !showCreateGroup && (
        <div className="empty-state">
          <Users size={48} />
          <p>No groups created yet</p>
          <button onClick={() => setShowCreateGroup(true)} className="btn-primary">
            Create Your First Group
          </button>
        </div>
      )}
    </div>
  )
}

function GroupCard({ group }) {
  return (
    <div className="group-card">
      <div className="group-header">
        <div>
          <h3>{group.display_name || group.group_name}</h3>
          <p className="group-id">@{group.group_name}</p>
        </div>
        <div className="group-stats">
          <span className="stat-badge users">
            <Users size={14} />
            {group.user_count || 0} users
          </span>
        </div>
      </div>

      {group.description && (
        <p className="group-description">{group.description}</p>
      )}

      <div className="group-footer">
        <button className="btn-link">
          <UserPlus size={16} />
          Manage Users
        </button>
        <button className="btn-link">
          <Bot size={16} />
          Manage Agents
        </button>
      </div>
    </div>
  )
}

function CreateGroupModal({ onClose, onCreate }) {
  const [formData, setFormData] = useState({
    group_name: '',
    display_name: '',
    description: '',
    created_by: 'admin' // TODO: Get from auth
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    onCreate(formData)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Create New Group</h2>
          <button onClick={onClose} className="modal-close">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label>Group ID (lowercase, no spaces)</label>
            <input
              type="text"
              value={formData.group_name}
              onChange={e => setFormData({ ...formData, group_name: e.target.value })}
              placeholder="analysts"
              pattern="[a-z_]+"
              required
            />
          </div>

          <div className="form-group">
            <label>Display Name</label>
            <input
              type="text"
              value={formData.display_name}
              onChange={e => setFormData({ ...formData, display_name: e.target.value })}
              placeholder="Data Analysts"
              required
            />
          </div>

          <div className="form-group">
            <label>Description (optional)</label>
            <textarea
              value={formData.description}
              onChange={e => setFormData({ ...formData, description: e.target.value })}
              placeholder="Team members who analyze data"
              rows={3}
            />
          </div>

          <div className="modal-actions">
            <button type="button" onClick={onClose} className="btn-secondary">
              Cancel
            </button>
            <button type="submit" className="btn-primary">
              Create Group
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default App
