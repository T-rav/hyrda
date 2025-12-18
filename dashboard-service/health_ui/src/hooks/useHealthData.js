import { useState, useEffect, useCallback } from 'react'
import { isTestMode, getTestScenario } from '../utils/testMockData'

export function useHealthData() {
  const [data, setData] = useState({
    health: null,
    metrics: null,
    ready: null,
    loading: true,
    error: null,
    lastUpdate: null
  })

  const fetchData = useCallback(async () => {
    try {
      // Don't set loading:true during refetch if we already have data
      // This prevents cards from disappearing while fetching updates
      setData(prev => ({ ...prev, loading: !prev.health, error: null }))

      // Check for test mode
      if (isTestMode()) {
        const scenario = getTestScenario()

        // Simulate loading delay
        await new Promise(resolve => setTimeout(resolve, 500))

        if (scenario === null) {
          // Simulate loading state
          setData(prev => ({ ...prev, loading: true }))
          return
        }

        if (scenario === 'fetch_error') {
          throw new Error('Simulated network error')
        }

        // Use mock data
        setData({
          health: scenario.health,
          metrics: scenario.metrics,
          ready: scenario.ready,
          loading: false,
          error: null,
          lastUpdate: new Date()
        })
        return
      }

      // Real API calls
      const [healthRes, metricsRes, readyRes] = await Promise.all([
        fetch('/api/health'),
        fetch('/api/metrics'),
        fetch('/api/ready')
      ])

      // Check if responses are ok
      if (!healthRes.ok) throw new Error(`Health endpoint failed: ${healthRes.status}`)
      if (!metricsRes.ok) throw new Error(`Metrics endpoint failed: ${metricsRes.status}`)
      if (!readyRes.ok) throw new Error(`Ready endpoint failed: ${readyRes.status}`)

      const [health, metrics, ready] = await Promise.all([
        healthRes.json(),
        metricsRes.json(),
        readyRes.json()
      ])

      // Always keep previous data and only update with valid new data
      setData(prev => ({
        health: (health && Object.keys(health).length > 0) ? health : (prev.health || health),
        metrics: (metrics && Object.keys(metrics).length > 0) ? metrics : (prev.metrics || metrics),
        ready: (ready && Object.keys(ready).length > 0) ? ready : (prev.ready || ready),
        loading: false,
        error: null,
        lastUpdate: new Date()
      }))
    } catch (error) {
      console.error('Error fetching health data:', error)
      setData(prev => ({
        ...prev,
        loading: false,
        error: error.message
      }))
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000) // Update every 10 seconds
    return () => clearInterval(interval)
  }, [fetchData])

  return {
    ...data,
    refetch: fetchData
  }
}
