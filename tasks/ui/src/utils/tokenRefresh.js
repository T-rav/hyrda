/**
 * Token Refresh Utility
 *
 * Provides automatic JWT token refresh using refresh tokens (OAuth 2.0 flow).
 * When an API call receives 401 Unauthorized, automatically attempts to refresh
 * the access token using the refresh token before retrying the request.
 */

let isRefreshing = false
let refreshSubscribers = []

/**
 * Subscribe to token refresh completion
 * @param {Function} callback - Function to call when refresh completes
 */
function subscribeTokenRefresh(callback) {
  refreshSubscribers.push(callback)
}

/**
 * Notify all subscribers that token refresh is complete
 * @param {string|null} newToken - New access token, or null if refresh failed
 */
function onTokenRefreshed(newToken) {
  refreshSubscribers.forEach((callback) => callback(newToken))
  refreshSubscribers = []
}

/**
 * Refresh the access token using the refresh token
 * @returns {Promise<boolean>} True if refresh succeeded, false otherwise
 */
async function refreshAccessToken() {
  try {
    const response = await fetch('https://localhost:6001/auth/token/refresh', {
      method: 'POST',
      credentials: 'include', // Send refresh token cookie
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (response.ok) {
      const data = await response.json()
      // New access token is automatically set in cookie by server
      console.log('✅ Access token refreshed successfully')
      return true
    }

    console.error('❌ Token refresh failed:', response.status)
    return false
  } catch (error) {
    console.error('❌ Token refresh error:', error)
    return false
  }
}

/**
 * Fetch with automatic token refresh on 401
 *
 * This wrapper automatically refreshes the access token if a request
 * receives 401 Unauthorized, then retries the original request.
 *
 * @param {string} url - URL to fetch
 * @param {Object} options - Fetch options
 * @returns {Promise<Response>} Fetch response
 *
 * @example
 * const response = await fetchWithTokenRefresh('/api/jobs', {
 *   method: 'GET',
 *   credentials: 'include'
 * })
 */
export async function fetchWithTokenRefresh(url, options = {}) {
  // Ensure credentials are included
  const fetchOptions = {
    ...options,
    credentials: 'include',
  }

  // Make initial request
  let response = await fetch(url, fetchOptions)

  // If 401 Unauthorized, try to refresh token
  if (response.status === 401) {
    // If already refreshing, wait for it to complete
    if (isRefreshing) {
      return new Promise((resolve) => {
        subscribeTokenRefresh(async (newToken) => {
          if (newToken) {
            // Retry with refreshed token
            const retryResponse = await fetch(url, fetchOptions)
            resolve(retryResponse)
          } else {
            // Refresh failed - redirect to login
            window.location.href =
              'https://localhost:6001/auth/start?redirect=https://localhost:5001'
            resolve(response)
          }
        })
      })
    }

    // Start refreshing
    isRefreshing = true

    try {
      const refreshed = await refreshAccessToken()

      if (refreshed) {
        // Token refreshed successfully - retry original request
        response = await fetch(url, fetchOptions)
        onTokenRefreshed(true)
      } else {
        // Refresh failed - redirect to login
        console.log('Token refresh failed, redirecting to login')
        onTokenRefreshed(null)
        window.location.href =
          'https://localhost:6001/auth/start?redirect=https://localhost:5001'
      }
    } finally {
      isRefreshing = false
    }
  }

  return response
}

/**
 * Setup automatic token refresh on app startup
 *
 * Checks token expiration and proactively refreshes if needed.
 * Call this once when the app initializes.
 */
export function setupTokenRefresh() {
  // Check token every 5 minutes and proactively refresh if < 2 minutes left
  setInterval(async () => {
    try {
      // Check if we have a valid session
      const response = await fetch('/auth/me', {
        credentials: 'include',
      })

      if (!response.ok) {
        // Session invalid - try to refresh
        console.log('Session check failed, attempting token refresh')
        await refreshAccessToken()
      }
    } catch (error) {
      console.error('Token check error:', error)
    }
  }, 5 * 60 * 1000) // Every 5 minutes
}
