export function formatUptime(seconds) {
  if (!seconds || seconds < 0) return '0m'

  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)

  if (days > 0) return `${days}d ${hours}h ${minutes}m`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

export function getOverallStatus(readyData) {
  if (!readyData) return 'unknown'
  return readyData.status === 'ready' ? 'healthy' : 'unhealthy'
}

export function getServiceDetails(service, serviceData, metricsData) {
  if (!serviceData) return 'Not configured'

  switch (service) {
    case 'cache':
      if (serviceData.status === 'healthy') {
        const conversations = serviceData.cached_conversations || 0
        const memory = metricsData?.cache?.memory_used || serviceData.memory_used || 'N/A'
        return `${conversations} conversations • ${memory} memory`
      }
      return serviceData.message || serviceData.error || 'Not configured'

    case 'langfuse':
      if (serviceData.status === 'healthy') {
        return `Observability enabled • ${serviceData.host || 'cloud.langfuse.com'}`
      } else if (serviceData.status === 'unhealthy') {
        return serviceData.message || 'Configuration error'
      }
      return serviceData.message || 'Disabled'

    case 'metrics':
      if (serviceData.status === 'healthy') {
        const activeConversations = metricsData?.active_conversations?.total || serviceData.active_conversations || 0
        return `Prometheus enabled • ${activeConversations} active conversations`
      }
      return serviceData.message || 'Disabled'

    case 'llm':
      return `${serviceData.provider || 'Unknown'} - ${serviceData.model || 'Unknown'}`

    default:
      return serviceData.message || serviceData.error || 'Unknown'
  }
}

export function shouldShowAsMetric(service, serviceData) {
  // Always show cache and metrics as metrics to prevent flickering
  switch (service) {
    case 'cache':
    case 'metrics':
      return true
    default:
      return false
  }
}

export function getMetricValue(service, serviceData, metricsData) {
  switch (service) {
    case 'cache':
      return metricsData?.cache?.memory_used || serviceData.memory_used || 'N/A'
    case 'metrics':
      return metricsData?.active_conversations?.total || serviceData.active_conversations || 0
    case 'rag':
      const ragData = metricsData?.rag_performance
      if (ragData && ragData.total_queries > 0) {
        return `${ragData.success_rate}%`
      }
      return 'No queries yet'
    default:
      return 'N/A'
  }
}

export function getMetricLabel(service, serviceData, metricsData) {
  switch (service) {
    case 'cache':
      return 'Memory Used'
    case 'metrics':
      return 'Active Conversations (4h)'
    case 'rag':
      const ragData = metricsData?.rag_performance
      if (ragData && ragData.total_queries > 0) {
        return `RAG Success Rate (${ragData.total_queries} queries)`
      }
      return 'RAG Performance'
    default:
      return 'Value'
  }
}
