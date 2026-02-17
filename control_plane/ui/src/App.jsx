import React, { useState, useEffect } from 'react'
import { Shield, Users, Bot, LogOut, User, Key, Target } from 'lucide-react'
import './App.css'
import AgentsView from './components/AgentsView'
import UsersView from './components/UsersView'
import GroupsView from './components/GroupsView'
import ServiceAccountsView from './components/ServiceAccountsView'
import GoalBotsView from './components/GoalBotsView'
import Toast from './components/Toast'
import { useAgents } from './hooks/useAgents'
import { useUsers } from './hooks/useUsers'
import { useGroups } from './hooks/useGroups'
import { usePermissions } from './hooks/usePermissions'
import { useServiceAccounts } from './hooks/useServiceAccounts'
import { useGoalBots } from './hooks/useGoalBots'
import { useToast } from './hooks/useToast'

function App() {
  // Get initial tab from URL path
  const getTabFromPath = () => {
    const path = window.location.pathname
    if (path === '/users') return 'users'
    if (path === '/groups') return 'groups'
    if (path === '/service-accounts') return 'service-accounts'
    if (path === '/goal-bots') return 'goal-bots'
    return 'agents' // default
  }

  const [activeTab, setActiveTab] = useState(getTabFromPath())

  // Update URL when tab changes
  const handleTabChange = (tab) => {
    setActiveTab(tab)
    const path = tab === 'agents' ? '/' : `/${tab}`
    window.history.pushState({}, '', path)
  }

  // Handle browser back/forward buttons
  useEffect(() => {
    const handlePopState = () => {
      setActiveTab(getTabFromPath())
    }
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  // Toast notifications
  const toast = useToast()

  // Custom hooks for data management
  const {
    agents,
    loading,
    error,
    selectedAgent,
    selectedAgentDetails,
    usageStats,
    setSelectedAgent,
    fetchAgents,
    refreshAgents,
    fetchAgentDetails,
    toggleAgent,
  } = useAgents(toast)

  const {
    users,
    syncing,
    currentUserEmail,
    fetchUsers,
    syncUsers,
    updateAdminStatus,
  } = useUsers(toast)

  const {
    groups,
    showCreateGroup,
    selectedGroup,
    setShowCreateGroup,
    setSelectedGroup,
    fetchGroups,
    createGroup,
    updateGroup,
    addUserToGroup,
    removeUserFromGroup,
    deleteGroup,
  } = useGroups(toast, fetchUsers)

  const {
    grantAgentToGroup,
    revokeAgentFromGroup,
  } = usePermissions(toast, fetchAgentDetails, fetchAgents)

  const {
    serviceAccounts,
    loading: serviceAccountsLoading,
    showCreateModal,
    createdApiKey,
    setShowCreateModal,
    setCreatedApiKey,
    fetchServiceAccounts,
    createServiceAccount,
    revokeServiceAccount,
    deleteServiceAccount,
    toggleActiveStatus,
  } = useServiceAccounts(toast)

  const {
    goalBots,
    loading: goalBotsLoading,
    error: goalBotsError,
    selectedBot,
    selectedBotDetails,
    showCreateModal: showGoalBotCreateModal,
    setSelectedBot,
    setShowCreateModal: setShowGoalBotCreateModal,
    fetchGoalBots,
    fetchBotDetails,
    createGoalBot,
    updateGoalBot,
    deleteGoalBot,
    toggleGoalBot,
    pauseGoalBot,
    resumeGoalBot,
    triggerGoalBot,
    cancelGoalBot,
    fetchBotRuns,
    fetchRunDetails,
    resetBotState,
  } = useGoalBots(toast)

  // Check authentication on mount to prevent back-button access after logout
  // Note: This is NOT aggressive - skips auth paths and let server-side auth handle it
  useEffect(() => {
    const verifyAuth = async () => {
      // Skip auth check if we're on an auth-related path
      const isAuthPath = window.location.pathname.startsWith('/auth/')
      if (isAuthPath) {
        return
      }

      try {
        const response = await fetch('/api/users/me', {
          credentials: 'include'
        })
        if (!response.ok) {
          // Not authenticated - redirect to login
          console.log('Not authenticated, redirecting to login')
          window.location.href = '/auth/login'
          return
        }
      } catch (error) {
        console.error('Auth check failed:', error)
        window.location.href = '/auth/login'
        return
      }
    }

    verifyAuth()
  }, [])

  // Initial data fetch
  useEffect(() => {
    document.title = 'InsightMesh - Control Plane'
    fetchAgents()
    fetchGroups()
    fetchUsers()
    fetchServiceAccounts()
    fetchGoalBots()
  }, [])

  // Logout handler
  const handleLogout = () => {
    // Use window.location to POST to logout endpoint
    // This allows the server's redirect to /auth/logged-out to work properly
    const form = document.createElement('form')
    form.method = 'POST'
    form.action = '/auth/logout'
    document.body.appendChild(form)
    form.submit()
  }

  // Fetch agent details when an agent is selected
  useEffect(() => {
    if (selectedAgent) {
      fetchAgentDetails(selectedAgent.name)
    }
  }, [selectedAgent])

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
              onClick={() => handleTabChange('agents')}
            >
              <Bot size={20} />
              Agents
            </button>
            <button
              className={`nav-link ${activeTab === 'service-accounts' ? 'active' : ''}`}
              onClick={() => handleTabChange('service-accounts')}
            >
              <Key size={20} />
              API Keys
            </button>
            <button
              className={`nav-link ${activeTab === 'goal-bots' ? 'active' : ''}`}
              onClick={() => handleTabChange('goal-bots')}
            >
              <Target size={20} />
              Goals
            </button>
            <button
              className={`nav-link ${activeTab === 'groups' ? 'active' : ''}`}
              onClick={() => handleTabChange('groups')}
            >
              <Users size={20} />
              Groups
            </button>
            <button
              className={`nav-link ${activeTab === 'users' ? 'active' : ''}`}
              onClick={() => handleTabChange('users')}
            >
              <Users size={20} />
              Users
            </button>
            <div className="logout-dropdown">
              <button
                className="nav-link logout-btn"
                onClick={handleLogout}
                title="Logout"
              >
                <LogOut size={20} />
                Logout
              </button>
              {currentUserEmail && (
                <div className="dropdown-menu">
                  <div className="dropdown-item user-email">
                    <User size={16} />
                    {currentUserEmail}
                  </div>
                </div>
              )}
            </div>
          </nav>
        </div>
      </header>

      <main className="main-content">
        {activeTab === 'agents' && (
          <AgentsView
            agents={agents}
            groups={groups}
            loading={loading}
            error={error}
            usageStats={usageStats}
            onRefresh={fetchAgents}
            onForceRefresh={refreshAgents}
            selectedAgent={selectedAgent}
            selectedAgentDetails={selectedAgentDetails}
            setSelectedAgent={setSelectedAgent}
            onGrantToGroup={grantAgentToGroup}
            onRevokeFromGroup={revokeAgentFromGroup}
            onToggle={toggleAgent}
          />
        )}
        {activeTab === 'users' && (
          <UsersView
            users={users}
            groups={groups}
            onRefresh={fetchUsers}
            onSync={syncUsers}
            syncing={syncing}
            onAddUserToGroup={addUserToGroup}
            onRemoveUserFromGroup={removeUserFromGroup}
            onUpdateAdminStatus={updateAdminStatus}
            currentUserEmail={currentUserEmail}
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
            onUpdateGroup={updateGroup}
            onAddUserToGroup={addUserToGroup}
            onRemoveUserFromGroup={removeUserFromGroup}
            onDeleteGroup={deleteGroup}
            onGrantAgent={grantAgentToGroup}
            onRevokeAgent={revokeAgentFromGroup}
            selectedGroup={selectedGroup}
            setSelectedGroup={setSelectedGroup}
          />
        )}
        {activeTab === 'service-accounts' && (
          <ServiceAccountsView
            serviceAccounts={serviceAccounts}
            agents={agents}
            loading={serviceAccountsLoading}
            onRefresh={() => fetchServiceAccounts()}
            showCreateModal={showCreateModal}
            setShowCreateModal={setShowCreateModal}
            onCreate={createServiceAccount}
            onRevoke={revokeServiceAccount}
            onDelete={deleteServiceAccount}
            onToggleActive={toggleActiveStatus}
            createdApiKey={createdApiKey}
            setCreatedApiKey={setCreatedApiKey}
          />
        )}
        {activeTab === 'goal-bots' && (
          <GoalBotsView
            goalBots={goalBots}
            agents={agents}
            loading={goalBotsLoading}
            error={goalBotsError}
            selectedBot={selectedBot}
            selectedBotDetails={selectedBotDetails}
            showCreateModal={showGoalBotCreateModal}
            setSelectedBot={setSelectedBot}
            setShowCreateModal={setShowGoalBotCreateModal}
            onRefresh={fetchGoalBots}
            onFetchDetails={fetchBotDetails}
            onCreate={createGoalBot}
            onUpdate={updateGoalBot}
            onDelete={deleteGoalBot}
            onToggle={toggleGoalBot}
            onPause={pauseGoalBot}
            onResume={resumeGoalBot}
            onTrigger={triggerGoalBot}
            onCancel={cancelGoalBot}
            onFetchRuns={fetchBotRuns}
            onFetchRunDetails={fetchRunDetails}
            onResetState={resetBotState}
          />
        )}
      </main>

      {/* Toast Notifications */}
      <div className="toast-container">
        {toast.toasts.map(t => (
          <Toast
            key={t.id}
            message={t.message}
            type={t.type}
            onClose={() => toast.removeToast(t.id)}
          />
        ))}
      </div>
    </div>
  )
}

export default App
