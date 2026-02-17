import React from 'react'
import { Clock, Loader } from 'lucide-react'

function GoalBotCard({ bot, onClick }) {
  const formatSchedule = () => {
    if (bot.schedule_type === 'cron') {
      return bot.schedule_config?.cron_expression || 'Custom'
    }
    const seconds = bot.schedule_config?.interval_seconds || 86400
    if (seconds >= 86400) {
      const days = Math.floor(seconds / 86400)
      return `Every ${days} day${days > 1 ? 's' : ''}`
    } else if (seconds >= 3600) {
      const hours = Math.floor(seconds / 3600)
      return `Every ${hours} hour${hours > 1 ? 's' : ''}`
    } else {
      const minutes = Math.floor(seconds / 60)
      return `Every ${minutes} min${minutes > 1 ? 's' : ''}`
    }
  }

  const formatNextRun = () => {
    if (!bot.next_run_at) return null
    const next = new Date(bot.next_run_at)
    const now = new Date()
    const diff = next - now

    if (diff <= 0) return 'Due now'

    const hours = Math.floor(diff / (1000 * 60 * 60))
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))

    if (hours >= 24) {
      const days = Math.floor(hours / 24)
      return `Due in ${days} day${days > 1 ? 's' : ''}`
    } else if (hours > 0) {
      return `Due in ${hours}h ${minutes}m`
    } else {
      return `Due in ${minutes}m`
    }
  }

  return (
    <div className="agent-card clickable" onClick={() => onClick(bot)}>
      <div className="agent-card-header">
        <div className="agent-info">
          <div className="agent-name-header">
            <h3>{bot.name}</h3>
            {bot.has_running_job && (
              <span className="stat-badge running">
                <Loader size={10} className="spin" />
                Running
              </span>
            )}
          </div>
        </div>
        <div>
          <span className={`stat-badge ${bot.is_enabled ? 'enabled' : 'disabled'}`}>
            {bot.is_enabled ? 'Active' : 'Disabled'}
          </span>
        </div>
      </div>

      <p className="agent-description">{bot.description}</p>

      <div className="agent-footer">
        <div className="agent-stats">
          <span className="stat-badge schedule">
            <Clock size={14} />
            {formatSchedule()}
          </span>
          {bot.is_enabled && formatNextRun() && (
            <span className="stat-badge next-run">
              {formatNextRun()}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

export default GoalBotCard
