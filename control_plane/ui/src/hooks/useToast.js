import { useState } from 'react'

export function useToast() {
  const [toasts, setToasts] = useState([])

  const showToast = (message, type = 'success') => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, message, type }])
  }

  const removeToast = (id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id))
  }

  const success = (message) => showToast(message, 'success')
  const error = (message) => showToast(message, 'error')

  return {
    toasts,
    removeToast,
    success,
    error,
  }
}
