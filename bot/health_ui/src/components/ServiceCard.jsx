import React from 'react'
import StatusCard from './StatusCard'
import MetricsCard from './MetricsCard'
import { shouldShowAsMetric, getMetricValue, getMetricLabel, getServiceDetails } from '../utils/statusHelpers'

function ServiceCard({ service, title, icon, serviceData, metricsData }) {
  const showAsMetric = shouldShowAsMetric(service, serviceData)

  if (showAsMetric) {
    return (
      <MetricsCard
        title={title}
        value={getMetricValue(service, serviceData, metricsData)}
        label={getMetricLabel(service, serviceData, metricsData)}
        icon={icon}
      />
    )
  }

  return (
    <StatusCard
      title={title}
      status={serviceData?.status || 'unknown'}
      details={getServiceDetails(service, serviceData, metricsData)}
      icon={icon}
    />
  )
}

export default ServiceCard
