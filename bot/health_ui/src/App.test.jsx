import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import App from './App'

// Mock API responses
const mockHealthData = {
  status: 'healthy',
  version: '1.0.0',
  timestamp: '2025-09-24T17:00:00Z'
}

const mockMetricsData = {
  uptime_seconds: 3600,  // 1 hour
  memory_usage_mb: 256,
  active_conversations: 5,
  total_requests: 1000
}

const mockReadyData = {
  status: 'ready',
  checks: {
    llm: {
      status: 'healthy',
      provider: 'openai',
      model: 'gpt-4o-mini'
    },
    cache: {
      status: 'healthy',
      memory_used_mb: 1.05
    },
    langfuse: {
      status: 'healthy',
      enabled: true,
      url: 'https://us.cloud.langfuse.com'
    },
    metrics: {
      status: 'healthy',
      enabled: true,
      endpoints: {
        metrics_json: '/api/metrics',
        prometheus: '/api/prometheus'
      }
    }
  }
}

const mockServicesData = {
  status: 'healthy',
  services: {
    task_scheduler: {
      name: 'Task Scheduler',
      status: 'healthy',
      details: {
        running: true,
        jobs_count: 1
      }
    },
    database: {
      name: 'MySQL Database',
      status: 'healthy',
      details: {
        host: 'mysql',
        port: '3306',
        databases: ['insightmesh_bot', 'insightmesh_task'],
        total_databases: 2
      }
    },
    elasticsearch: {
      name: 'Elasticsearch',
      status: 'healthy',
      details: {
        cluster_status: 'green',
        nodes: 1,
        active_shards: 2
      }
    }
  }
}

describe('Health Dashboard App', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/health')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHealthData)
        })
      }
      if (url.includes('/api/metrics')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockMetricsData)
        })
      }
      if (url.includes('/api/ready')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockReadyData)
        })
      }
      if (url.includes('/api/services/health')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockServicesData)
        })
      }
      return Promise.reject(new Error('Unknown URL'))
    })
  })

  test('renders health dashboard header with correct title', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('InsightMesh Health Dashboard')).toBeInTheDocument()
    })
  })

  test('ensures Health Dashboard title consistency', async () => {
    render(<App />)

    await waitFor(() => {
      // Verify the main header title is exactly "InsightMesh Health Dashboard"
      const mainTitle = screen.getByText('InsightMesh Health Dashboard')
      expect(mainTitle).toBeInTheDocument()
      expect(mainTitle.tagName).toBe('H1')
    })
  })

  test('verifies Health Dashboard title does not change unexpectedly', async () => {
    render(<App />)

    await waitFor(() => {
      // This test ensures the title remains "InsightMesh Health Dashboard" and not something else
      expect(screen.getByText('InsightMesh Health Dashboard')).toBeInTheDocument()

      // Ensure it's not the Tasks Dashboard title
      expect(screen.queryByText('InsightMesh Tasks')).not.toBeInTheDocument()

      // Ensure it's not a generic title
      expect(screen.queryByText('InsightMesh Dashboard')).not.toBeInTheDocument()
    })
  })

  test('verifies HTML page title matches expected Health Dashboard title', async () => {
    render(<App />)

    // Wait for useEffect to set the document title
    await waitFor(() => {
      expect(document.title).toBe('InsightMesh - Health Dashboard')
    })

    // Ensure it's not the Tasks Dashboard title
    expect(document.title).not.toBe('InsightMesh - Tasks Dashboard')
  })

  test('displays loading spinner initially', () => {
    render(<App />)

    // Should show loading initially
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  test('loads and displays health data', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('InsightMesh Health Dashboard')).toBeInTheDocument()
    })

    // Check if API calls were made
    expect(global.fetch).toHaveBeenCalledWith('/api/health')
    expect(global.fetch).toHaveBeenCalledWith('/api/metrics')
    expect(global.fetch).toHaveBeenCalledWith('/api/ready')
  })

  test('displays overall status badge', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/🟢 Healthy/i)).toBeInTheDocument()
    })
  })

  test('displays last update time', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getAllByText(/Last updated:/i)[0]).toBeInTheDocument()
    })
  })

  test('displays services section', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Infrastructure')).toBeInTheDocument()
    })
  })

  test('displays infrastructure section', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Infrastructure')).toBeInTheDocument()
    })
  })

  test('handles API errors gracefully', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('API Error'))

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument()
    })
  })

  test('refresh button works', async () => {
    const user = userEvent.setup()
    render(<App />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh now/i })).toBeInTheDocument()
    })

    const refreshButton = screen.getByRole('button', { name: /refresh now/i })
    await user.click(refreshButton)

    // Should make API calls again (initial load + refresh)
    expect(global.fetch).toHaveBeenCalled()
  })

  test('displays API endpoints section when metrics are available', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('API Endpoints')).toBeInTheDocument()
    })
  })

  test('API endpoint links have correct attributes', async () => {
    render(<App />)

    await waitFor(() => {
      const metricsLink = screen.getByRole('link', { name: /metrics \(json\)/i })
      expect(metricsLink).toHaveAttribute('href', '/api/metrics')
      expect(metricsLink).toHaveAttribute('target', '_blank')
      expect(metricsLink).toHaveAttribute('rel', 'noopener noreferrer')
    })
  })

  test('displays system uptime from metrics endpoint correctly', async () => {
    render(<App />)

    await waitFor(() => {
      // uptime_seconds: 3600 = 1 hour = "1h 0m"
      expect(screen.getByText('1h 0m')).toBeInTheDocument()
    })
  })

  test('uptime shows 0m when metrics are unavailable', async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/health')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHealthData)
        })
      }
      if (url.includes('/api/metrics')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({}) // No uptime_seconds
        })
      }
      if (url.includes('/api/ready')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockReadyData)
        })
      }
      if (url.includes('/api/services/health')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockServicesData)
        })
      }
      return Promise.reject(new Error('Unknown URL'))
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('0m')).toBeInTheDocument()
    })
  })

  test('uptime formats days correctly', async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/health')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHealthData)
        })
      }
      if (url.includes('/api/metrics')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            ...mockMetricsData,
            uptime_seconds: 90061 // 1 day, 1 hour, 1 minute
          })
        })
      }
      if (url.includes('/api/ready')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockReadyData)
        })
      }
      if (url.includes('/api/services/health')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockServicesData)
        })
      }
      return Promise.reject(new Error('Unknown URL'))
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('1d 1h 1m')).toBeInTheDocument()
    })
  })
})

describe('Health Dashboard Title Consistency Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/health')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHealthData)
        })
      }
      if (url.includes('/api/metrics')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockMetricsData)
        })
      }
      if (url.includes('/api/ready')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockReadyData)
        })
      }
      if (url.includes('/api/services/health')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockServicesData)
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    })
  })

  test('maintains consistent Health Dashboard branding', async () => {
    render(<App />)

    // Wait for useEffect to set the document title
    await waitFor(() => {
      expect(document.title).toBe('InsightMesh - Health Dashboard')
    })

    // Wait for the data to load and the title to appear
    await waitFor(() => {
      expect(screen.getByText('InsightMesh Health Dashboard')).toBeInTheDocument()
    })
  })

  test('prevents accidental title changes to Tasks Dashboard', async () => {
    render(<App />)

    await waitFor(() => {
      // Ensure Health Dashboard elements are present
      expect(screen.getByText('InsightMesh Health Dashboard')).toBeInTheDocument()

      // Ensure Tasks Dashboard elements are NOT present
      expect(screen.queryByText('InsightMesh Tasks')).not.toBeInTheDocument()
      expect(screen.queryByText('Tasks Dashboard')).not.toBeInTheDocument()
    })
  })

  test('ensures Health Dashboard maintains correct context', async () => {
    render(<App />)

    await waitFor(() => {
      // Verify Health Dashboard specific elements
      expect(screen.getByText('InsightMesh Health Dashboard')).toBeInTheDocument()
      expect(screen.getByText('Infrastructure')).toBeInTheDocument()

      // Verify HTML title is correct
      expect(document.title).toBe('InsightMesh - Health Dashboard')
    })
  })
})

describe('Infrastructure Services Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/health')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHealthData)
        })
      }
      if (url.includes('/api/metrics')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockMetricsData)
        })
      }
      if (url.includes('/api/ready')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockReadyData)
        })
      }
      if (url.includes('/api/services/health')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockServicesData)
        })
      }
      return Promise.reject(new Error('Unknown URL'))
    })
  })

  test('displays infrastructure services correctly', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Infrastructure')).toBeInTheDocument()
      expect(screen.getByText('Task Scheduler')).toBeInTheDocument()
      expect(screen.getByText('MySQL Database')).toBeInTheDocument()
      expect(screen.getByText('Elasticsearch')).toBeInTheDocument()
    })
  })

  test('displays service status badges', async () => {
    render(<App />)

    await waitFor(() => {
      const healthyBadges = screen.getAllByText('healthy')
      expect(healthyBadges.length).toBeGreaterThan(0)
    })
  })

  test('displays service details', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('running:')).toBeInTheDocument()
      expect(screen.getByText('Yes')).toBeInTheDocument()
      expect(screen.getByText('jobs count:')).toBeInTheDocument()
      // Use getAllByText since there might be multiple "1"s on the page
      expect(screen.getAllByText('1')[0]).toBeInTheDocument()
    })
  })

  test('displays database list correctly', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('databases:')).toBeInTheDocument()
      expect(screen.getByText('insightmesh_bot, insightmesh_task')).toBeInTheDocument()
    })
  })

  test('handles services API error', async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/services/health')) {
        return Promise.reject(new Error('Services API Error'))
      }
      if (url.includes('/api/health')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHealthData)
        })
      }
      if (url.includes('/api/metrics')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockMetricsData)
        })
      }
      if (url.includes('/api/ready')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockReadyData)
        })
      }
      return Promise.reject(new Error('Unknown URL'))
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Infrastructure')).toBeInTheDocument()
      expect(screen.getByText(/error loading services/i)).toBeInTheDocument()
    })
  })

  test('displays sections in correct order: Infrastructure before Lifetime Statistics', async () => {
    // Add lifetime stats to mock metrics
    const metricsWithLifetimeStats = {
      ...mockMetricsData,
      lifetime_stats: {
        total_traces: 150,
        unique_threads: 25,
        since_date: '2025-01-01',
        description: 'Statistics since January 2025'
      }
    }

    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/health')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHealthData)
        })
      }
      if (url.includes('/api/metrics')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(metricsWithLifetimeStats)
        })
      }
      if (url.includes('/api/ready')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockReadyData)
        })
      }
      if (url.includes('/api/services/health')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockServicesData)
        })
      }
      return Promise.reject(new Error('Unknown URL'))
    })

    render(<App />)

    await waitFor(() => {
      // Get all h2 headings (section titles)
      const headings = screen.getAllByRole('heading', { level: 2 })
      const headingTexts = headings.map(h => h.textContent)

      // Find the indices
      const infrastructureIndex = headingTexts.findIndex(text => text.includes('Infrastructure'))
      const lifetimeStatsIndex = headingTexts.findIndex(text => text.includes('Lifetime Statistics'))

      // Both sections should be present
      expect(infrastructureIndex).toBeGreaterThan(-1)
      expect(lifetimeStatsIndex).toBeGreaterThan(-1)

      // Infrastructure should appear before Lifetime Statistics
      expect(infrastructureIndex).toBeLessThan(lifetimeStatsIndex)
    })
  })
})
