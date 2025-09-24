import React from 'react'
import './App.css'

function App() {
  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <div className="header-title">
            <h1>InsightMesh Tasks - React Test</h1>
          </div>
        </div>
      </header>

      <main className="main-content">
        <div className="glass-card">
          <h2>🎉 React UI is Working!</h2>
          <p>This is the React version of the tasks UI.</p>
          <p>API Test: Fetching from localhost:5001/api/scheduler/info</p>

          <button onClick={() => {
            fetch('/api/scheduler/info')
              .then(r => r.json())
              .then(data => alert('API Response: ' + JSON.stringify(data)))
              .catch(err => alert('API Error: ' + err.message))
          }}>
            Test API Call
          </button>
        </div>
      </main>

      <footer className="footer">
        <p>InsightMesh Tasks v1.0.0</p>
      </footer>
    </div>
  )
}

export default App
