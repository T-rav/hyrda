import React, { useState, useEffect } from 'react'
import { Shield, Users, Activity, Bot, UserPlus, Plus, X, Trash2, RefreshCw, CheckCircle } from 'lucide-react'
import './App.css'

function App() {
  const [activeTab, setActiveTab] = useState('agents')
  const [agents, setAgents] = useState([])
  const [groups, setGroups] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreateGroup, setShowCreateGroup] = useState(false)
  const [selectedGroup, setSelectedGroup] = useState(null)
  const [selectedUser, setSelectedUser] = useState(null)
  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    document.title = 'InsightMesh - Control Plane'
    fetchAgents()
    fetchGroups()
    fetchUsers()
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
      setGroups([])
    }
  }

  const fetchUsers = async () => {
    try {
      const response = await fetch('/api/users')
      if (!response.ok) throw new Error('Failed to fetch users')
      const data = await response.json()
      setUsers(data.users || [])
    } catch (err) {
      console.error('Error fetching users:', err)
      setUsers([])
    }
  }

  const syncUsers = async () => {
    try {
      setSyncing(true)
      const response = await fetch('/api/users/sync', { method: 'POST' })
      if (!response.ok) throw new Error('Failed to sync users')
      const data = await response.json()
      alert(`Sync complete: ${data.stats.created} created, ${data.stats.updated} updated`)
      fetchUsers()
    } catch (err) {
      alert(`Error: ${err.message}`)
    } finally {
      setSyncing(false)
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

  const addUserToGroup = async (groupName, userId) => {
    try {
      const response = await fetch(`/api/groups/${groupName}/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, added_by: 'admin' })
      })
      if (!response.ok) throw new Error('Failed to add user')
      fetchGroups()
      alert('User added to group successfully')
    } catch (err) {
      alert(`Error: ${err.message}`)
    }
  }

  const removeUserFromGroup = async (groupName, userId) => {
    try {
      const response = await fetch(`/api/groups/${groupName}/users?user_id=${userId}`, {
        method: 'DELETE'
      })
      if (!response.ok) throw new Error('Failed to remove user')
      fetchGroups()
      alert('User removed from group successfully')
    } catch (err) {
      alert(`Error: ${err.message}`)
    }
  }

  const grantAgentToGroup = async (groupName, agentName) => {
    try {
      const response = await fetch(`/api/groups/${groupName}/agents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_name: agentName, granted_by: 'admin' })
      })
      if (!response.ok) throw new Error('Failed to grant agent access')
      alert('Agent access granted to group')
    } catch (err) {
      alert(`Error: ${err.message}`)
    }
  }

  const revokeAgentFromGroup = async (groupName, agentName) => {
    try {
      const response = await fetch(`/api/groups/${groupName}/agents?agent_name=${agentName}`, {
        method: 'DELETE'
      })
      if (!response.ok) throw new Error('Failed to revoke agent access')
      alert('Agent access revoked from group')
    } catch (err) {
      alert(`Error: ${err.message}`)
    }
  }

  const grantAgentToUser = async (userId, agentName) => {
    try {
      const response = await fetch(`/api/users/${userId}/permissions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_name: agentName, granted_by: 'admin' })
      })
      if (!response.ok) throw new Error('Failed to grant permission')
      alert('Permission granted to user')
    } catch (err) {
      alert(`Error: ${err.message}`)
    }
  }

  const revokeAgentFromUser = async (userId, agentName) => {
    try {
      const response = await fetch(`/api/users/${userId}/permissions?agent_name=${agentName}`, {
        method: 'DELETE'
      })
      if (!response.ok) throw new Error('Failed to revoke permission')
      alert('Permission revoked from user')
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
              className={`nav-link ${activeTab === 'users' ? 'active' : ''}`}
              onClick={() => setActiveTab('users')}
            >
              <Users size={20} />
              Users
            </button>
            <button
              className={`nav-link ${activeTab === 'groups' ? 'active' : ''}`}
              onClick={() => setActiveTab('groups')}
            >
              <Users size={20} />
              Groups
            </button>
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
        {activeTab === 'users' && (
          <UsersView
            users={users}
            agents={agents}
            onRefresh={fetchUsers}
            onSync={syncUsers}
            syncing={syncing}
            onGrantAgent={grantAgentToUser}
            onRevokeAgent={revokeAgentFromUser}
            selectedUser={selectedUser}
            setSelectedUser={setSelectedUser}
          />
        )}
        {activeTab === 'groups' && (
          <GroupsView
            groups={groups}
            users={users}
            agents={agents}
            onRefresh={fetchGroups}
            showCreateGroup={showCreateGroup}
            setShowCreateGroup={setShowCreateGroup}
            onCreateGroup={createGroup}
            onAddUserToGroup={addUserToGroup}
            onRemoveUserFromGroup={removeUserFromGroup}
            onGrantAgent={grantAgentToGroup}
            onRevokeAgent={revokeAgentFromGroup}
            selectedGroup={selectedGroup}
            setSelectedGroup={setSelectedGroup}
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
          <RefreshCw size={16} />
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

function UsersView({ users, agents, onRefresh, onSync, syncing, onGrantAgent, onRevokeAgent, selectedUser, setSelectedUser }) {
  return (
    <div className="content-section">
      <div className="section-header">
        <h2>Users ({users.length})</h2>
        <div>
          <button onClick={onRefresh} className="btn-secondary">
            <RefreshCw size={16} />
            Refresh
          </button>
          <button
            onClick={onSync}
            className="btn-primary"
            disabled={syncing}
            style={{ marginLeft: '0.5rem' }}
          >
            <RefreshCw size={16} className={syncing ? 'spinning' : ''} />
            Sync from Slack
          </button>
        </div>
      </div>

      <div className="users-list">
        {users.map(user => (
          <UserCard
            key={user.id}
            user={user}
            agents={agents}
            onGrantAgent={onGrantAgent}
            onRevokeAgent={onRevokeAgent}
            isSelected={selectedUser?.id === user.id}
            onClick={() => setSelectedUser(user)}
          />
        ))}
      </div>

      {users.length === 0 && (
        <div className="empty-state">
          <Users size={48} />
          <p>No users synced yet</p>
          <button onClick={onSync} className="btn-primary" disabled={syncing}>
            Sync Users from Slack
          </button>
        </div>
      )}

      {selectedUser && (
        <PermissionModal
          title={`Manage Permissions: ${selectedUser.full_name}`}
          agents={agents}
          onClose={() => setSelectedUser(null)}
          onGrant={(agentName) => onGrantAgent(selectedUser.slack_user_id, agentName)}
          onRevoke={(agentName) => onRevokeAgent(selectedUser.slack_user_id, agentName)}
        />
      )}
    </div>
  )
}

function UserCard({ user, agents, onGrantAgent, onRevokeAgent, isSelected, onClick }) {
  return (
    <div className={`user-card ${isSelected ? 'selected' : ''}`} onClick={onClick}>
      <div className="user-header">
        <div>
          <h3>{user.full_name}</h3>
          <p className="user-email">{user.email}</p>
        </div>
        <div className="user-badges">
          {user.is_admin && <span className="badge admin">Admin</span>}
          {user.is_active ? (
            <span className="badge active">Active</span>
          ) : (
            <span className="badge inactive">Inactive</span>
          )}
        </div>
      </div>
      <div className="user-footer">
        <span className="user-id">{user.slack_user_id}</span>
        {user.last_synced_at && (
          <span className="user-sync">
            Synced: {new Date(user.last_synced_at).toLocaleDateString()}
          </span>
        )}
      </div>
    </div>
  )
}

function GroupsView({
  groups,
  users,
  agents,
  onRefresh,
  showCreateGroup,
  setShowCreateGroup,
  onCreateGroup,
  onAddUserToGroup,
  onRemoveUserFromGroup,
  onGrantAgent,
  onRevokeAgent,
  selectedGroup,
  setSelectedGroup
}) {
  const [showManageUsers, setShowManageUsers] = useState(false)
  const [showManageAgents, setShowManageAgents] = useState(false)

  const handleManageUsers = (group) => {
    setSelectedGroup(group)
    setShowManageUsers(true)
  }

  const handleManageAgents = (group) => {
    setSelectedGroup(group)
    setShowManageAgents(true)
  }

  return (
    <div className="content-section">
      <div className="section-header">
        <h2>Permission Groups ({groups.length})</h2>
        <div>
          <button onClick={onRefresh} className="btn-secondary">
            <RefreshCw size={16} />
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

      {showManageUsers && selectedGroup && (
        <ManageGroupUsersModal
          group={selectedGroup}
          users={users}
          onClose={() => {
            setShowManageUsers(false)
            setSelectedGroup(null)
            onRefresh()
          }}
          onAddUser={(userId) => onAddUserToGroup(selectedGroup.group_name, userId)}
          onRemoveUser={(userId) => onRemoveUserFromGroup(selectedGroup.group_name, userId)}
        />
      )}

      {showManageAgents && selectedGroup && (
        <PermissionModal
          title={`Manage Agents: ${selectedGroup.display_name}`}
          agents={agents}
          onClose={() => {
            setShowManageAgents(false)
            setSelectedGroup(null)
          }}
          onGrant={(agentName) => onGrantAgent(selectedGroup.group_name, agentName)}
          onRevoke={(agentName) => onRevokeAgent(selectedGroup.group_name, agentName)}
        />
      )}

      <div className="groups-list">
        {groups.map(group => (
          <GroupCard
            key={group.group_name}
            group={group}
            onManageUsers={handleManageUsers}
            onManageAgents={handleManageAgents}
          />
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

function GroupCard({ group, onManageUsers, onManageAgents }) {
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
        <button className="btn-link" onClick={() => onManageUsers(group)}>
          <UserPlus size={16} />
          Manage Users
        </button>
        <button className="btn-link" onClick={() => onManageAgents(group)}>
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
    created_by: 'admin'
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

function ManageGroupUsersModal({ group, users, onClose, onAddUser, onRemoveUser }) {
  const [searchTerm, setSearchTerm] = useState('')

  const filteredUsers = users.filter(user =>
    user.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.email.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content large" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Manage Users: {group.display_name}</h2>
          <button onClick={onClose} className="modal-close">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <div className="form-group">
            <input
              type="text"
              placeholder="Search users..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="search-input"
            />
          </div>

          <div className="user-selection-list">
            {filteredUsers.map(user => (
              <div key={user.id} className="user-selection-item">
                <div>
                  <div className="user-name">{user.full_name}</div>
                  <div className="user-email">{user.email}</div>
                </div>
                <div>
                  <button
                    onClick={() => onAddUser(user.slack_user_id)}
                    className="btn-sm btn-primary"
                  >
                    <Plus size={14} />
                    Add
                  </button>
                  <button
                    onClick={() => onRemoveUser(user.slack_user_id)}
                    className="btn-sm btn-danger"
                    style={{ marginLeft: '0.5rem' }}
                  >
                    <Trash2 size={14} />
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="modal-actions">
          <button onClick={onClose} className="btn-primary">
            Done
          </button>
        </div>
      </div>
    </div>
  )
}

function PermissionModal({ title, agents, onClose, onGrant, onRevoke }) {
  const [selectedAgent, setSelectedAgent] = useState('')

  const handleGrant = () => {
    if (selectedAgent) {
      onGrant(selectedAgent)
      setSelectedAgent('')
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button onClick={onClose} className="modal-close">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <div className="form-group">
            <label>Select Agent</label>
            <select
              value={selectedAgent}
              onChange={e => setSelectedAgent(e.target.value)}
              className="agent-select"
            >
              <option value="">-- Select an agent --</option>
              {agents.map(agent => (
                <option key={agent.name} value={agent.name}>
                  /{agent.name} - {agent.description}
                </option>
              ))}
            </select>
          </div>

          <div className="permission-actions">
            <button
              onClick={handleGrant}
              disabled={!selectedAgent}
              className="btn-primary"
            >
              <CheckCircle size={16} />
              Grant Access
            </button>
            <button
              onClick={() => selectedAgent && onRevoke(selectedAgent)}
              disabled={!selectedAgent}
              className="btn-danger"
            >
              <Trash2 size={16} />
              Revoke Access
            </button>
          </div>

          <div className="agent-list">
            <h4>Available Agents</h4>
            {agents.map(agent => (
              <div key={agent.name} className="agent-list-item">
                <strong>/{agent.name}</strong>
                <p>{agent.description}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="modal-actions">
          <button onClick={onClose} className="btn-secondary">
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export default App
