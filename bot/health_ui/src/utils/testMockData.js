// Mock data for testing different UI states
export const mockHealthData = {
  healthy: {
    status: 'healthy',
    uptime_seconds: 3661,
    timestamp: '2024-01-15T10:30:00Z',
    version: '1.2.0'
  },
  unhealthy: {
    status: 'unhealthy',
    uptime_seconds: 120,
    timestamp: '2024-01-15T10:30:00Z',
    version: '1.2.0'
  }
}

export const mockReadyData = {
  healthy: {
    status: 'ready',
    checks: {
      llm_api: {
        status: 'healthy',
        provider: 'openai',
        model: 'gpt-4o-mini'
      },
      cache: {
        status: 'healthy',
        memory_used: '45.2MB',
        cached_conversations: 3,
        redis_url: 'redis://localhost:6379'
      },
      langfuse: {
        status: 'healthy',
        enabled: true,
        configured: true,
        host: 'https://cloud.langfuse.com'
      },
      metrics: {
        status: 'healthy',
        enabled: true,
        active_conversations: 3,
        endpoints: {
          metrics_json: '/api/metrics',
          prometheus: '/api/prometheus'
        }
      },
      configuration: {
        status: 'healthy',
        missing_variables: 'none'
      }
    }
  },
  mixed: {
    status: 'not_ready',
    checks: {
      llm_api: {
        status: 'healthy',
        provider: 'openai',
        model: 'gpt-4o-mini'
      },
      cache: {
        status: 'disabled',
        message: 'Cache service not configured - using Slack API only'
      },
      langfuse: {
        status: 'unhealthy',
        enabled: false,
        configured: true,
        message: 'Enabled but client failed to initialize - check credentials and host',
        host: 'https://cloud.langfuse.com'
      },
      metrics: {
        status: 'healthy',
        enabled: true,
        active_conversations: 1,
        endpoints: {
          metrics_json: '/api/metrics',
          prometheus: '/api/prometheus'
        }
      },
      configuration: {
        status: 'unhealthy',
        missing_variables: 'LANGFUSE_SECRET_KEY'
      }
    }
  },
  offline: {
    status: 'not_ready',
    checks: {
      llm_api: {
        status: 'unhealthy',
        error: 'API connection failed'
      },
      cache: {
        status: 'unhealthy',
        error: 'Redis connection failed',
        message: 'Configured but Redis unavailable at redis://localhost:6379'
      },
      langfuse: {
        status: 'disabled',
        enabled: false,
        configured: false,
        package_available: false,
        message: 'Langfuse package not installed (pip install langfuse)'
      },
      metrics: {
        status: 'disabled',
        enabled: false,
        prometheus_available: false,
        message: 'Prometheus client not available - install prometheus-client package'
      },
      configuration: {
        status: 'unhealthy',
        missing_variables: 'SLACK_BOT_TOKEN, SLACK_APP_TOKEN, LLM_API_KEY'
      }
    }
  }
}

export const mockMetricsData = {
  healthy: {
    uptime_seconds: 3661,
    start_time: '2024-01-15T09:30:00Z',
    current_time: '2024-01-15T10:30:00Z',
    cache: {
      status: 'available',
      memory_used: '45.2MB',
      cached_conversations: 3,
      redis_url: 'redis://localhost:6379'
    },
    active_conversations: {
      total: 3,
      tracked_by_metrics: 2,
      cached_conversations: 3,
      description: 'Active conversations being tracked'
    },
    services: {
      langfuse: {
        enabled: true,
        available: true
      },
      metrics: {
        enabled: true,
        available: true
      },
      cache: {
        available: true
      }
    }
  },
  minimal: {
    uptime_seconds: 120,
    start_time: '2024-01-15T10:28:00Z',
    current_time: '2024-01-15T10:30:00Z',
    services: {
      langfuse: {
        enabled: false,
        available: false
      },
      metrics: {
        enabled: true,
        available: true
      },
      cache: {
        available: false
      }
    }
  }
}

// Test scenarios
export const testScenarios = {
  'All Healthy': {
    health: mockHealthData.healthy,
    ready: mockReadyData.healthy,
    metrics: mockMetricsData.healthy
  },
  'Mixed Status': {
    health: mockHealthData.healthy,
    ready: mockReadyData.mixed,
    metrics: mockMetricsData.minimal
  },
  'All Offline': {
    health: mockHealthData.unhealthy,
    ready: mockReadyData.offline,
    metrics: mockMetricsData.minimal
  },
  'Loading State': null, // Simulates loading
  'Network Error': 'fetch_error' // Simulates fetch error
}

// Test mode flag for development
export const isTestMode = () => {
  return new URLSearchParams(window.location.search).get('test') === 'true'
}

// Get test scenario from URL
export const getTestScenario = () => {
  const scenario = new URLSearchParams(window.location.search).get('scenario')
  return testScenarios[scenario] || null
}
