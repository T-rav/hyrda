import { useState, useEffect, useCallback } from 'react'

export function useHumanInput() {
  const [requests, setRequests] = useState({})

  // Poll for human input requests every 3 seconds
  useEffect(() => {
    const poll = async () => {
      try {
        const resp = await fetch('/api/human-input')
        if (resp.ok) setRequests(await resp.json())
      } catch { /* ignore */ }
    }
    poll()
    const interval = setInterval(poll, 3000)
    return () => clearInterval(interval)
  }, [])

  const submit = useCallback(async (issueNumber, answer) => {
    try {
      await fetch(`/api/human-input/${issueNumber}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer }),
      })
      setRequests((prev) => {
        const next = { ...prev }
        delete next[issueNumber]
        return next
      })
    } catch { /* ignore */ }
  }, [])

  return { requests, submit }
}
