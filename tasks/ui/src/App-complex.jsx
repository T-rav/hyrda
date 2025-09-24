import React, { useState } from 'react'
import { CalendarClock, LayoutDashboard, ListChecks, Activity } from 'lucide-react'
import ErrorBoundary from './components/ErrorBoundary'
import LoadingSpinner from './components/LoadingSpinner'
import ErrorMessage from './components/ErrorMessage'
import Dashboard from './components/Dashboard'
import TasksList from './components/TasksList'
import './App.css'

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleTabChange = (tab) => {
    setActiveTab(tab)
  }

  const handleError = (error) => {
    setError(error)
  }

  const clearError = () => {
    setError(null)
  }

  if (loading && activeTab === 'dashboard') {
    return <LoadingSpinner />
  }

  return (
    <ErrorBoundary>
      <div className="app">
        {/* Header - Match Health UI style */}
        <header className="header">
          <div className="header-content">
            <div className="header-title">
              <CalendarClock className="header-icon" size={28} />
              <h1>InsightMesh Tasks</h1>
            </div>
            <nav className="header-nav">
              <button
                className={`nav-link ${activeTab === 'dashboard' ? 'active' : ''}`}
                onClick={() => handleTabChange('dashboard')}
              >
                <LayoutDashboard size={20} />
                Dashboard
              </button>
              <button
                className={`nav-link ${activeTab === 'tasks' ? 'active' : ''}`}
                onClick={() => handleTabChange('tasks')}
              >
                <ListChecks size={20} />
                Tasks
              </button>
              <a
                href="http://localhost:8080/ui"
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

        <main className="main">
          {error && <ErrorMessage error={error} onRetry={clearError} />}

          <div className="main-content">
            {activeTab === 'dashboard' && (
              <Dashboard
                onError={handleError}
                setLoading={setLoading}
              />
            )}
            {activeTab === 'tasks' && (
              <TasksList
                onError={handleError}
                setLoading={setLoading}
              />
            )}
          </div>
        </main>

        <footer className="footer">
          <p>InsightMesh Tasks v1.0.0 • Auto-refresh every 10 seconds</p>
        </footer>
      </div>
    </ErrorBoundary>
  )
}

export default App
