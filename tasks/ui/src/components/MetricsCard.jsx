import React from 'react'
import { TrendingUp } from 'lucide-react'
import './MetricsCard.css'

function MetricsCard({ title, value, label, icon, trend }) {
  return (
    <div className="metrics-card">
      <div className="metrics-card-header">
        <div className="metrics-card-title">
          {icon && <span className="metrics-icon">{icon}</span>}
          <h3>{title}</h3>
        </div>
        {trend && (
          <div className={`trend-indicator ${trend > 0 ? 'positive' : 'negative'}`}>
            <TrendingUp size={16} className={trend < 0 ? 'trend-down' : ''} />
            <span>{Math.abs(trend)}%</span>
          </div>
        )}
      </div>

      <div className="metrics-card-content">
        <div className="metric-value">
          {value}
        </div>
        <div className="metric-label">
          {label}
        </div>
      </div>
    </div>
  )
}

export default MetricsCard
