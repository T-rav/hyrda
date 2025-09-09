import React from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

function ErrorMessage({ error, onRetry }) {
  return (
    <div className="error-message">
      <div className="error-content">
        <AlertTriangle size={24} className="error-icon" />
        <div className="error-text">
          <h3>Failed to load health data</h3>
          <p>{error}</p>
        </div>
        {onRetry && (
          <button onClick={onRetry} className="retry-button">
            <RefreshCw size={16} />
            Retry
          </button>
        )}
      </div>
    </div>
  )
}

export default ErrorMessage
