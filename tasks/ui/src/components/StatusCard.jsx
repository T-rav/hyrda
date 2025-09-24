import React from 'react'
import { CheckCircle, AlertCircle, XCircle, HelpCircle } from 'lucide-react'
import './StatusCard.css'

function StatusCard({ title, status, details, icon, fullWidth = false }) {
  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
      case 'ready':
        return <CheckCircle className="status-icon healthy" size={20} />
      case 'unhealthy':
      case 'not_ready':
        return <XCircle className="status-icon unhealthy" size={20} />
      case 'disabled':
        return <AlertCircle className="status-icon disabled" size={20} />
      default:
        return <HelpCircle className="status-icon unknown" size={20} />
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
      case 'ready':
        return 'healthy'
      case 'unhealthy':
      case 'not_ready':
        return 'unhealthy'
      case 'disabled':
        return 'disabled'
      default:
        return 'unknown'
    }
  }

  return (
    <div className={`status-card ${fullWidth ? 'full-width' : ''}`}>
      <div className="status-card-header">
        <div className="status-card-title">
          {icon && <span className="title-icon">{icon}</span>}
          <h3>{title}</h3>
        </div>
        <div className="status-indicator">
          {getStatusIcon(status)}
          <span className={`status-text ${getStatusColor(status)}`}>
            {status === 'ready' ? 'Healthy' : status?.charAt(0).toUpperCase() + status?.slice(1) || 'Unknown'}
          </span>
        </div>
      </div>

      {details && (
        <div className="status-card-details">
          <p>{details}</p>
        </div>
      )}
    </div>
  )
}

export default StatusCard
