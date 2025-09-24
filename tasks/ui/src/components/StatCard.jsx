import React from 'react'

const variantStyles = {
  primary: 'stat-card-primary',
  success: 'stat-card-success',
  warning: 'stat-card-warning',
  info: 'stat-card-info',
  danger: 'stat-card-danger'
}

function StatCard({ title, value, icon, variant = 'primary' }) {
  const variantClass = variantStyles[variant] || variantStyles.primary

  return (
    <div className={`glass-card stat-card ${variantClass}`}>
      <div className="stat-content">
        <div className="stat-info">
          <h3 className="stat-number">{value}</h3>
          <p className="stat-label">{title}</p>
        </div>
        <div className="stat-icon">
          {icon}
        </div>
      </div>
    </div>
  )
}

export default StatCard
