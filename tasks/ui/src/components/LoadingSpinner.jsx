import React from 'react'
import { Activity } from 'lucide-react'

function LoadingSpinner({ message = 'Loading health dashboard...' }) {
  return (
    <div className="loading">
      <Activity className="loading-icon" size={32} />
      <p>{message}</p>
    </div>
  )
}

export default LoadingSpinner
