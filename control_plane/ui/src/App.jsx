import React, { useState, useEffect } from 'react'
import { Shield, Users, Bot } from 'lucide-react'
import './App.css'
import AgentsView from './components/AgentsView'
import UsersView from './components/UsersView'
import GroupsView from './components/GroupsView'

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
  const [selectedAgent, setSelectedAgent] = useState(null)
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
      const response = await fetch('/api/users/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      })
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
            users={users}
            groups={groups}
            loading={loading}
            error={error}
            onRefresh={fetchAgents}
            selectedAgent={selectedAgent}
            setSelectedAgent={setSelectedAgent}
            onGrantToUser={grantAgentToUser}
            onRevokeFromUser={revokeAgentFromUser}
            onGrantToGroup={grantAgentToGroup}
            onRevokeFromGroup={revokeAgentFromGroup}
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

export default App
