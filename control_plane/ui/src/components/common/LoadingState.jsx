import React from 'react'
import { Loader2 } from 'lucide-react'

/**
 * LoadingState component for loading indicators
 *
 * @typedef {Object} LoadingStateProps
 * @property {string} [message='Loading...'] - Loading message
 * @property {string} [size='md'] - Spinner size (sm, md, lg)
 * @property {boolean} [centered=true] - Center the loading state
 * @property {string} [className] - Additional CSS classes
 * @property {boolean} [fullscreen=false] - Fullscreen overlay
 */

const SIZES = {
  sm: 16,
  md: 24,
  lg: 48,
}

function LoadingState({
  message = 'Loading...',
  size = 'md',
  centered = true,
  className = '',
  fullscreen = false,
}) {
  const iconSize = SIZES[size] || SIZES.md

  const classes = [
    'loading-state',
    centered && 'loading-state-centered',
    fullscreen && 'loading-state-fullscreen',
    className,
  ].filter(Boolean).join(' ')

  const content = (
    <>
      <Loader2
        size={iconSize}
        className="loading-state-spinner"
        aria-hidden="true"
      />
      {message && (
        <span className="loading-state-message">{message}</span>
      )}
    </>
  )

  if (fullscreen) {
    return (
      <div className={classes} role="status" aria-live="polite">
        <div className="loading-state-content">
          {content}
        </div>
      </div>
    )
  }

  return (
    <div className={classes} role="status" aria-live="polite">
      {content}
    </div>
  )
}

export default LoadingState
