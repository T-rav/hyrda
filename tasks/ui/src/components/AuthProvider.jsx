import React, { createContext, useContext, useEffect, useState } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const response = await fetch('/auth/me', {
        credentials: 'include'
      })

      if (response.ok) {
        const data = await response.json()
        if (data.authenticated) {
          setUser(data.user)
        } else {
          // Not authenticated - redirect to control-plane OAuth
          const currentUrl = window.location.href
          const controlPlaneUrl = import.meta.env.VITE_CONTROL_PLANE_URL || 'https://localhost:6001'
          window.location.href = `${controlPlaneUrl}/auth/login?redirect=${encodeURIComponent(currentUrl)}`
          return
        }
      } else if (response.status === 401) {
        // Not authenticated - redirect to control-plane OAuth
        const currentUrl = window.location.href
        const controlPlaneUrl = import.meta.env.VITE_CONTROL_PLANE_URL || 'https://localhost:6001'
        window.location.href = `${controlPlaneUrl}/auth/login?redirect=${encodeURIComponent(currentUrl)}`
        return
      } else {
        setError('Failed to check authentication')
      }
    } catch (err) {
      console.error('Auth check failed:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const logout = async () => {
    try {
      await fetch('/auth/logout', {
        method: 'POST',
        credentials: 'include'
      })
      setUser(null)
      // Redirect to login
      const currentUrl = window.location.origin
      const controlPlaneUrl = import.meta.env.VITE_CONTROL_PLANE_URL || 'https://localhost:6001'
      window.location.href = `${controlPlaneUrl}/auth/login?redirect=${encodeURIComponent(currentUrl)}`
    } catch (err) {
      console.error('Logout failed:', err)
      setError(err.message)
    }
  }

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner"></div>
        <p>Checking authentication...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="error-screen">
        <h2>Authentication Error</h2>
        <p>{error}</p>
        <button onClick={checkAuth}>Retry</button>
      </div>
    )
  }

  return (
    <AuthContext.Provider value={{ user, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
